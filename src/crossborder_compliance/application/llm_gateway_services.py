"""Security-gated invocation, not an Agent or compliance workflow."""

import json
import math
from collections.abc import Iterator

from jsonschema import Draft202012Validator

from crossborder_compliance.application.llm_gateway_policy import (
    ModelRouter,
    ModelUsagePolicyService,
)
from crossborder_compliance.application.llm_gateway_redaction import DataRedactionService
from crossborder_compliance.domain.llm_gateway import (
    GatewayAuditEvent,
    GatewayDenied,
    LLMResult,
    LLMStreamEvent,
    ModelOperation,
    ProviderFailure,
    ProviderInput,
)


def validate_schema(schema):
    def walk(value):
        if isinstance(value, dict):
            for key in ("$ref", "$dynamicRef", "$recursiveRef"):
                if key in value and not str(value[key]).startswith("#"):
                    raise GatewayDenied("REMOTE_SCHEMA_REFERENCE_DENIED")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    try:
        walk(schema)
        Draft202012Validator.check_schema(schema)
    except Exception:
        raise GatewayDenied("OUTPUT_SCHEMA_INVALID") from None


class LLMService:
    def __init__(self, *, context, configuration, inputs, providers, audit, redaction=None):
        self.context, self.configuration, self.inputs = context, configuration, inputs
        self.providers, self.audit, self.redaction = providers, audit, redaction
        self.policy = ModelUsagePolicyService()
        self.router = ModelRouter()

    def _audit(self, request, code, *, model=None, decision=None, redaction=None):
        try:
            self.audit.record(
                GatewayAuditEvent(
                    request_id=request.request_id,
                    tenant_id=self.context.tenant_id,
                    project_id=request.project_id,
                    analysis_snapshot_id=request.analysis_snapshot_id,
                    operation=request.operation,
                    model_id=model.model_id if model else None,
                    policy_versions=decision.policy_versions if decision else (),
                    redaction_run_id=redaction.run_id if redaction else None,
                    reason_code=code,
                )
            )
        except Exception:
            raise GatewayDenied("GATEWAY_AUDIT_UNAVAILABLE") from None

    def _prepare(self, request):
        self.configuration.authorize(request)
        items = self.inputs.load(self.context, request.project_id, request.input_refs)
        if tuple(item.ref for item in items) != request.input_refs:
            raise GatewayDenied("RESOURCE_NOT_FOUND")
        for item in items:
            if (
                item.tenant_id != self.context.tenant_id
                or item.project_id != request.project_id
                or (
                    not self.context.permission.system
                    and (
                        not set(item.required_scopes) <= self.context.permission.scopes
                        or (
                            item.organization_id is not None
                            and item.organization_id != self.context.user_context.organization_id
                        )
                    )
                )
            ):
                raise GatewayDenied("RESOURCE_NOT_FOUND")
        policies = self.configuration.policies(request)
        models = self.configuration.models(request)
        decision = self.policy.evaluate(request, self.context, items, policies, models)
        candidates = self.router.route(request, decision, models)
        candidates = tuple(
            m
            for m in candidates
            if m.provider_type in self.providers
            and request.operation in self.providers[m.provider_type].supported_operations
        )
        if not candidates:
            raise GatewayDenied("NO_ALLOWED_PROVIDER_CAPABILITY")
        self.configuration.pin_models(request, candidates)
        prompt = self.configuration.prompt(request)
        if request.output_schema:
            validate_schema(request.output_schema)
        texts = tuple(t for item in items for t in item.texts)
        return policies, decision, candidates, prompt, texts

    def _payload(self, request, model, policies, decision, prompt, texts):
        redaction = None
        schema = request.output_schema
        if decision.redaction_required and not self.policy.internal(model, policies):
            if self.redaction is None:
                raise GatewayDenied("REDACTION_SERVICE_REQUIRED")
            # Include trusted prompt and schema as well as all resource bodies in the proof.
            parts = ((prompt,) if prompt is not None else ()) + texts
            if schema is not None:
                parts += (json.dumps(schema),)
            redaction = self.redaction.redact(parts, request.input_refs, decision.policy_versions)
            DataRedactionService.validate(
                redaction, parts, request.input_refs, decision.policy_versions
            )
            masked = redaction.redacted_texts
            if prompt is not None:
                prompt, masked = masked[0], masked[1:]
            if schema is not None:
                try:
                    schema, masked = json.loads(masked[-1]), masked[:-1]
                    validate_schema(schema)
                except Exception:
                    raise GatewayDenied("REDACTION_NOT_VALIDATED") from None
            texts = masked
        return ProviderInput(
            operation=request.operation,
            texts=texts,
            system_prompt=prompt,
            output_schema=schema,
            max_output_tokens=request.max_output_tokens,
        ), redaction

    @staticmethod
    def _validate_result(request, model, payload, result):
        try:
            op = request.operation
            if op == ModelOperation.CHAT and result.text is None:
                raise ValueError()
            if op == ModelOperation.STRUCTURED_OUTPUT:
                if result.structured is None:
                    raise ValueError()
                Draft202012Validator(payload.output_schema).validate(result.structured)
            if op == ModelOperation.EMBEDDING:
                if (
                    model.embedding_dimension is None
                    or len(result.embeddings) != len(payload.texts)
                    or any(len(v) != model.embedding_dimension for v in result.embeddings)
                    or any(not math.isfinite(x) for v in result.embeddings for x in v)
                ):
                    raise ValueError()
            if op == ModelOperation.RERANK:
                if len(set(result.ranked_indices)) != len(result.ranked_indices) or any(
                    not 0 <= i < len(payload.texts) - 1 for i in result.ranked_indices
                ):
                    raise ValueError()
            if op == ModelOperation.COUNT_TOKENS and result.token_count is None:
                raise ValueError()
            if op == ModelOperation.HEALTH_CHECK and result.healthy is None:
                raise ValueError()
        except Exception:
            raise GatewayDenied("MODEL_RESULT_INVALID") from None

    def invoke(self, request):
        if request.operation == ModelOperation.CHAT_STREAM:
            raise GatewayDenied("USE_STREAM_CONTRACT")
        try:
            policies, decision, candidates, prompt, texts = self._prepare(request)
            for model in candidates:
                provider = self.providers.get(model.provider_type)
                if provider is None:
                    continue
                payload, redaction = self._payload(
                    request, model, policies, decision, prompt, texts
                )
                self.configuration.revalidate(request, model)
                self._audit(request, "ALLOWED", model=model, decision=decision, redaction=redaction)
                try:
                    result = provider.execute(model, payload)
                except ProviderFailure:
                    self._audit(request, "PROVIDER_FAILED", model=model, decision=decision)
                    continue
                except Exception:
                    raise GatewayDenied("MODEL_PROVIDER_FAILED") from None
                self._validate_result(request, model, payload, result)
                self._audit(
                    request, "COMPLETED", model=model, decision=decision, redaction=redaction
                )
                return LLMResult(
                    request_id=request.request_id,
                    model_id=model.model_id,
                    deployment_id=model.deployment_id,
                    provider_version_id=model.provider_version_id,
                    analysis_snapshot_id=request.analysis_snapshot_id,
                    policy=decision,
                    redaction_run_id=redaction.run_id if redaction else None,
                    result=result,
                )
            raise GatewayDenied("NO_ALLOWED_PROVIDER_AVAILABLE")
        except GatewayDenied:
            self._audit(request, "DENIED")
            raise
        except Exception:
            self._audit(request, "DENIED")
            raise GatewayDenied("MODEL_OPERATION_DENIED") from None

    def chat_stream(self, request) -> Iterator[LLMStreamEvent]:
        self._require_operation(request, ModelOperation.CHAT_STREAM)
        try:
            policies, decision, candidates, prompt, texts = self._prepare(request)
            for model in candidates:
                provider = self.providers.get(model.provider_type)
                if provider is None:
                    continue
                payload, redaction = self._payload(
                    request, model, policies, decision, prompt, texts
                )
                self.configuration.revalidate(request, model)
                self._audit(request, "ALLOWED", model=model, decision=decision, redaction=redaction)
                emitted = False
                try:
                    for sequence, delta in enumerate(provider.stream(model, payload)):
                        self.configuration.revalidate(request, model)
                        if not isinstance(delta, str):
                            raise GatewayDenied("MODEL_RESULT_INVALID")
                        emitted = True
                        yield LLMStreamEvent(
                            request_id=request.request_id,
                            model_id=model.model_id,
                            deployment_id=model.deployment_id,
                            sequence=sequence,
                            text_delta=delta,
                        )
                    if not emitted:
                        raise ProviderFailure()
                    self._audit(request, "COMPLETED", model=model, decision=decision)
                    return
                except ProviderFailure:
                    self._audit(request, "STREAM_FAILED", model=model, decision=decision)
                    if emitted:
                        raise GatewayDenied("PARTIAL_STREAM_FAILED") from None
                    continue
            raise GatewayDenied("NO_ALLOWED_PROVIDER_AVAILABLE")
        except GatewayDenied:
            self._audit(request, "DENIED")
            raise
        except Exception:
            self._audit(request, "DENIED")
            raise GatewayDenied("MODEL_OPERATION_DENIED") from None

    @staticmethod
    def _require_operation(request, operation):
        if request.operation != operation:
            raise GatewayDenied("OPERATION_CONTRACT_MISMATCH")

    def chat(self, request):
        self._require_operation(request, ModelOperation.CHAT)
        return self.invoke(request)

    def structured_output(self, request):
        self._require_operation(request, ModelOperation.STRUCTURED_OUTPUT)
        return self.invoke(request)

    def embedding(self, request):
        self._require_operation(request, ModelOperation.EMBEDDING)
        return self.invoke(request)

    def rerank(self, request):
        self._require_operation(request, ModelOperation.RERANK)
        return self.invoke(request)

    def count_tokens(self, request):
        self._require_operation(request, ModelOperation.COUNT_TOKENS)
        return self.invoke(request)

    def health_check(self, request):
        self._require_operation(request, ModelOperation.HEALTH_CHECK)
        return self.invoke(request)

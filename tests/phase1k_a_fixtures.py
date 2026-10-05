"""Explicit deterministic test adapters; never a production provider default."""

from uuid import uuid4

from crossborder_compliance.application.llm_gateway_redaction import input_digest
from crossborder_compliance.application.llm_gateway_services import LLMService
from crossborder_compliance.domain.llm_gateway import (
    AuthorizedInput,
    DetectionResult,
    GatewayDenied,
    InputReference,
    LLMRequest,
    ModelCandidate,
    ModelOperation,
    ModelUsagePolicy,
    ProviderFailure,
    ProviderResult,
    SensitiveSpan,
)
from crossborder_compliance.domain.metadata import ModelCapabilityCode
from crossborder_compliance.domain.security import RepositoryContext


class FakeInputSource:
    def __init__(self, items):
        self.items = items

    def load(self, context, project_id, refs):
        return tuple(self.items[r] for r in refs)


class FakeConfiguration:
    def __init__(self, policies, models):
        self.policy_rows, self.model_rows = policies, models
        self.pinned = None
        self.revoked = False
        self.prompt_text = None

    def authorize(self, request):
        if self.revoked:
            raise GatewayDenied("RESOURCE_NOT_FOUND")

    def policies(self, request):
        return self.policy_rows

    def models(self, request):
        return self.model_rows

    def pin_models(self, request, models):
        self.pinned = models

    def prompt(self, request):
        return self.prompt_text

    def revalidate(self, request, model):
        self.authorize(request)


class FakeAudit:
    def __init__(self):
        self.events = []
        self.fail = False

    def record(self, event):
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.events.append(event)


class FakeDetector:
    def __init__(self, literal="PRIVATE-123"):
        self.literal = literal
        self.complete = True
        self.review = False
        self.fail = False

    def detect(self, texts):
        if self.fail:
            raise ValueError("PRIVATE-123 detector must not echo")
        spans = []
        for i, t in enumerate(texts):
            start = 0
            while (pos := t.find(self.literal, start)) >= 0:
                spans.append(
                    SensitiveSpan(
                        part_index=i,
                        start=pos,
                        end=pos + len(self.literal),
                        sensitive_type="GENERIC_SENSITIVE_TOKEN",
                    )
                )
                start = pos + len(self.literal)
        return DetectionResult(
            input_hash=input_digest(texts),
            complete=self.complete,
            spans=tuple(spans),
            reviewer_required=self.review,
        )


class FakeProvider:
    supported_operations = frozenset(ModelOperation)

    def __init__(self):
        self.calls = []
        self.fail_models = set()
        self.after_first = False

    def execute(self, model, payload):
        self.calls.append((model, payload))
        if model.model_id in self.fail_models:
            raise ProviderFailure()
        op = payload.operation
        if op == ModelOperation.EMBEDDING:
            return ProviderResult(embeddings=tuple((1.0, 0.0) for _ in payload.texts))
        if op == ModelOperation.RERANK:
            return ProviderResult(ranked_indices=tuple(reversed(range(len(payload.texts) - 1))))
        if op == ModelOperation.STRUCTURED_OUTPUT:
            return ProviderResult(structured={"value": "ok"})
        if op == ModelOperation.COUNT_TOKENS:
            return ProviderResult(token_count=4)
        if op == ModelOperation.HEALTH_CHECK:
            return ProviderResult(healthy=True)
        return ProviderResult(text="test response")

    def stream(self, model, payload):
        self.calls.append((model, payload))
        if model.model_id in self.fail_models:
            raise ProviderFailure()
        yield "first"
        if self.after_first:
            raise ProviderFailure()
        yield "second"


def fixture():
    tenant, project, snap = uuid4(), uuid4(), uuid4()
    context = RepositoryContext.user(
        tenant, "actor", {"llm:invoke", f"project:{project}:read", "resource:read"}
    )
    ref = InputReference(resource_type="GENERIC_KNOWLEDGE", resource_id=uuid4(), version_id=uuid4())
    item = AuthorizedInput(
        ref=ref,
        tenant_id=tenant,
        project_id=project,
        required_scopes=("resource:read",),
        texts=("query PRIVATE-123", "document PRIVATE-123"),
        security_codes=("GENERIC_OPEN",),
        confidentiality_codes=("GENERIC_CONF_OPEN",),
        document_types=("GENERIC_INTERNAL_DOCUMENT",),
        permitted_model_boundaries=("TENANT",),
    )
    models = tuple(
        ModelCandidate(
            tenant_id=tenant,
            model_id=uuid4(),
            deployment_id=uuid4(),
            provider_id=uuid4(),
            provider_version_id=uuid4(),
            provider_version=1,
            provider_type="GENERIC_REST",
            deployment_class=cls,
            trust_level="APPROVED",
            data_boundary="TENANT",
            capabilities=tuple(ModelCapabilityCode),
            operations=tuple(ModelOperation),
            health_status="HEALTHY",
            max_output_tokens=4096,
            embedding_dimension=2,
            priority=i,
        )
        for i, cls in enumerate(("EXTERNAL_API", "PRIVATE_CLOUD", "PUBLIC_CLOUD"))
    )
    payload = dict(
        default_mode="EXTERNAL_MODEL_ALLOWED",
        security_rules={
            "GENERIC_OPEN": "EXTERNAL_MODEL_ALLOWED",
            "GENERIC_RESTRICTED": "INTERNAL_MODEL_ONLY",
        },
        confidentiality_rules={
            "GENERIC_CONF_OPEN": "EXTERNAL_MODEL_ALLOWED",
            "GENERIC_CONFIDENTIAL": "REDACTION_REQUIRED",
        },
        document_rules={"GENERIC_INTERNAL_DOCUMENT": "EXTERNAL_MODEL_ALLOWED"},
        allowed_model_ids=tuple(m.model_id for m in models),
        allowed_provider_ids=tuple(m.provider_id for m in models),
        allowed_trust_levels=("APPROVED",),
        allowed_data_boundaries=("TENANT",),
        allowed_operations=tuple(ModelOperation),
    )
    policies = tuple(
        ModelUsagePolicy(
            policy_id=uuid4(),
            version_id=uuid4(),
            version=1,
            tenant_id=tenant,
            scope_type=scope,
            project_id=project if scope == "PROJECT" else None,
            **payload,
        )
        for scope in ("TENANT", "PROJECT")
    )
    configuration = FakeConfiguration(policies, models)
    source = FakeInputSource({ref: item})
    provider = FakeProvider()
    audit = FakeAudit()
    service = LLMService(
        context=context,
        configuration=configuration,
        inputs=source,
        providers={"GENERIC_REST": provider},
        audit=audit,
    )
    request = LLMRequest(
        project_id=project, analysis_snapshot_id=snap, operation="chat", input_refs=(ref,)
    )
    return dict(
        tenant=tenant,
        project=project,
        snapshot=snap,
        context=context,
        ref=ref,
        item=item,
        models=models,
        policies=policies,
        source=source,
        provider=provider,
        audit=audit,
        configuration=configuration,
        service=service,
        request=request,
    )

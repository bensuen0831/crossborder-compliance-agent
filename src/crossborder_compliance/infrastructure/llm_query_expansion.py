"""Evidence-gap planner over the sole gateway. Output is search text, never evidence."""

import json
import os
from uuid import UUID

from pydantic import Field
from sqlalchemy import select

from crossborder_compliance.application.llm_model_catalog import SnapshotModelConfigurationQuery
from crossborder_compliance.domain.knowledge import Contract
from crossborder_compliance.domain.llm_gateway import (
    AuthorizedInput,
    GatewayDenied,
    InputReference,
    LLMRequest,
    ProviderFailure,
)
from crossborder_compliance.domain.llm_invocation import InvocationFacts
from crossborder_compliance.infrastructure.llm_enhancement_composition import enhancement_invocation
from crossborder_compliance.infrastructure.llm_gateway_configuration import PostgresLLMConfiguration
from crossborder_compliance.infrastructure.llm_invocation_governance import (
    PostgresLLMInvocationGovernance,
)
from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore
from crossborder_compliance.infrastructure.persistence import retrieval_models as g


class ExpandedQueries(Contract):
    search_phrases: tuple[str, ...] = Field(max_length=8)


class RetrievalGapInput:
    def __init__(self, config, query, gaps):
        self.config, self.query, self.gaps = config, query, gaps
        self.ref = InputReference(
            resource_type="RETRIEVAL_RUN",
            resource_id=UUID(gaps.retrieval_run_id),
            version_id=UUID(query.analysis_snapshot_id),
        )

    def load(self, context, project_id, refs):
        if refs != (self.ref,) or str(project_id) != self.query.project_id:
            raise LookupError("retrieval input not found")
        with self.config.sessions() as s:
            row = s.scalar(
                select(g.RetrievalRunEntity).where(
                    g.RetrievalRunEntity.tenant_id == str(context.tenant_id),
                    g.RetrievalRunEntity.project_id == str(project_id),
                    g.RetrievalRunEntity.analysis_snapshot_id == self.query.analysis_snapshot_id,
                    g.RetrievalRunEntity.retrieval_run_id == str(self.ref.resource_id),
                    g.RetrievalRunEntity.owner_actor_id == context.permission.actor_id,
                    g.RetrievalRunEntity.status == "RUNNING",
                )
            )
            if row is None:
                raise LookupError("retrieval input not found")
        return (
            AuthorizedInput(
                ref=self.ref,
                tenant_id=context.tenant_id,
                project_id=project_id,
                required_scopes=("knowledge:retrieve",),
                texts=(
                    json.dumps(
                        {
                            "original_query": self.query.query_text,
                            "missing_topics": self.gaps.missing_topics,
                            "reason_codes": self.gaps.reason_codes,
                            "instruction": "Return candidate search phrases only; never supply legal evidence or alter scope.",
                        }
                    ),
                ),
            ),
        )


class GovernedEvidenceGapQueryPlanner:
    def __init__(self, config, query, secrets, *, redaction=None):
        self.config, self.query, self.secrets = config, query, secrets
        self.redaction = redaction

    def plan(self, query_text, gaps):
        if gaps.status not in {"INSUFFICIENT", "PARTIALLY_SUFFICIENT"}:
            return ()
        if (
            gaps.analysis_snapshot_id != self.query.analysis_snapshot_id
            or gaps.project_id != self.query.project_id
        ):
            raise PermissionError("query expansion scope mismatch")
        prompts = self.config._saved(
            SnapshotModelConfigurationQuery(
                project_id=UUID(self.query.project_id),
                analysis_snapshot_id=UUID(self.query.analysis_snapshot_id),
            ),
            "LLM_PURPOSE_PROMPT",
        )
        prompt = next((p for p in prompts if p["logical_key"] == "QUERY_EXPANSION"), None)
        if not prompt or self.secrets is None:
            return ()
        inputs = RetrievalGapInput(
            self.config, self.query.model_copy(update={"query_text": query_text}), gaps
        )
        request = LLMRequest(
            project_id=UUID(gaps.project_id),
            analysis_snapshot_id=UUID(gaps.analysis_snapshot_id),
            operation="structured_output",
            input_refs=(inputs.ref,),
            prompt_id=UUID(prompt["object_id"]),
            output_schema=ExpandedQueries.model_json_schema(),
        )
        try:
            policy, _ = PostgresLLMInvocationGovernance(self.config).load(request)
            result = enhancement_invocation(
                self.config, inputs, self.secrets, redaction=self.redaction
            ).invoke(
                request,
                InvocationFacts(
                    trigger="KNOWLEDGE_EVIDENCE_INSUFFICIENT",
                    purpose="QUERY_EXPANSION",
                    evidence_sufficient=False,
                ),
            )
        except (GatewayDenied, ProviderFailure):
            return ()  # Ordinary missing enhancement capability cannot manufacture sufficiency.
        phrases = []
        for outcome in result.model_results:
            if outcome.result is None:
                continue
            output = ExpandedQueries.model_validate(outcome.result.result.structured)
            for phrase in output.search_phrases:
                phrase = " ".join(phrase.split())
                if phrase and len(phrase) <= 1000 and phrase not in phrases:
                    phrases.append(phrase)
        return tuple(phrases[: policy.query_expansion_limit])


def query_expansion_planner(sessions, context, query, *, secrets=None, redaction=None):
    if (
        secrets is None
        and os.environ.get("LLM_SECRET_STORE_ROOT")
        and os.environ.get("LLM_SECRET_STORE_KEY")
    ):
        secrets = EncryptedFileSecretStore(
            os.environ["LLM_SECRET_STORE_ROOT"],
            os.environ["LLM_SECRET_STORE_KEY"].encode(),
            context.tenant_id,
        )
    return GovernedEvidenceGapQueryPlanner(
        PostgresLLMConfiguration(sessions, context, frozen_snapshot=True),
        query,
        secrets,
        redaction=redaction,
    )

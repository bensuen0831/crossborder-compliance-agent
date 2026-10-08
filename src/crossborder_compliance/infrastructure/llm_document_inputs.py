"""Real document parser enhancement at confirmed-input preparation, before E resolution."""

import hashlib
import json
import os
from uuid import UUID

from sqlalchemy import select

from crossborder_compliance.application.document_services import DocumentParseService
from crossborder_compliance.application.llm_document_extraction import (
    DocumentSemanticExtractionService,
)
from crossborder_compliance.application.llm_model_catalog import SnapshotModelConfigurationQuery
from crossborder_compliance.domain.llm_document_candidates import DocumentCandidateExtraction
from crossborder_compliance.domain.llm_gateway import (
    AuthorizedInput,
    GatewayDenied,
    InputReference,
    LLMRequest,
)
from crossborder_compliance.infrastructure.document_parsers import default_native_parsers
from crossborder_compliance.infrastructure.document_storage import FileObjectStorageAdapter
from crossborder_compliance.infrastructure.llm_enhancement_composition import enhancement_invocation
from crossborder_compliance.infrastructure.llm_gateway_configuration import PostgresLLMConfiguration
from crossborder_compliance.infrastructure.llm_invocation_governance import (
    PostgresLLMInvocationGovernance,
)
from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore
from crossborder_compliance.infrastructure.persistence import document_models as d
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.document_repositories import (
    PostgresDocumentIntelligenceRepository,
)


class PinnedDocumentInput:
    """Only the bound genuine parse run in this snapshot can be read on invocation."""

    def __init__(self, configuration, repository, snapshot_id, fact_types=()):
        self.configuration, self.repository = configuration, repository
        self.snapshot_id = snapshot_id
        self.fact_types = tuple(fact_types)
        self.bound = None

    def bind(self, run_id, nodes):
        run = self.repository.get_parse_run(run_id)
        version_id = UUID(run["document_version_id"])
        self.repository.pin_parse_run(
            analysis_snapshot_id=self.snapshot_id,
            document_version_id=version_id,
            parse_run_id=run_id,
        )
        self.bound = InputReference(
            resource_type="DOCUMENT_PARSE_RUN", resource_id=run_id, version_id=version_id
        )
        return self.bound

    def load(self, context, project_id, refs):
        if refs != (self.bound,) or context.tenant_id != self.configuration.context.tenant_id:
            raise LookupError("document input not found")
        with self.configuration.sessions() as s:
            snapshot = s.get(b.AnalysisSnapshotEntity, str(self.snapshot_id))
            version = (
                s.get(b.ProjectVersionEntity, snapshot.project_version_id) if snapshot else None
            )
            pin = s.scalar(
                select(d.AnalysisSnapshotParseRunPinEntity).where(
                    d.AnalysisSnapshotParseRunPinEntity.tenant_id == str(context.tenant_id),
                    d.AnalysisSnapshotParseRunPinEntity.analysis_snapshot_id
                    == str(self.snapshot_id),
                    d.AnalysisSnapshotParseRunPinEntity.parse_run_id == str(self.bound.resource_id),
                    d.AnalysisSnapshotParseRunPinEntity.document_version_id
                    == str(self.bound.version_id),
                )
            )
            link = (
                s.scalar(
                    select(d.ProjectVersionDocumentLinkEntity.link_id).where(
                        d.ProjectVersionDocumentLinkEntity.project_version_id
                        == snapshot.project_version_id,
                        d.ProjectVersionDocumentLinkEntity.tenant_id == str(context.tenant_id),
                        d.ProjectVersionDocumentLinkEntity.document_version_id
                        == str(self.bound.version_id),
                    )
                )
                if snapshot
                else None
            )
            if (
                not snapshot
                or not version
                or not pin
                or not link
                or snapshot.tenant_id != str(context.tenant_id)
                or version.tenant_id != str(context.tenant_id)
                or version.project_id != str(project_id)
                or version.status not in {"CONFIRMED", "SUPERSEDED"}
            ):
                raise LookupError("document input not found")
        nodes = self.repository.list_structure(self.bound.resource_id)
        if sum(len(node.get("original_text") or "") for node in nodes) > 200_000:
            raise GatewayDenied("DOCUMENT_SEMANTIC_INPUT_TOO_LARGE")
        return (
            AuthorizedInput(
                ref=self.bound,
                tenant_id=context.tenant_id,
                project_id=project_id,
                required_scopes=("document:read",),
                texts=(
                            json.dumps(
                                {"allowed_fact_types": self.fact_types, "source_nodes": [
                            {
                                "source_node_id": node["structure_node_id"],
                                "text": node.get("original_text") or node.get("normalized_text"),
                            }
                            for node in nodes
                            if node.get("original_text") or node.get("normalized_text")
                                ]}
                    ),
                ),
            ),
        )


def prepare_document_candidates(
    sessions, context, intake, snapshot_id, *, storage=None, secrets=None, redaction=None
):
    config = PostgresLLMConfiguration(sessions, context, frozen_snapshot=True)
    selection = config._saved(
        SnapshotModelConfigurationQuery(
            project_id=intake.project_id, analysis_snapshot_id=snapshot_id
        ),
        "LLM_SELECTION",
    )
    if not selection or selection[0]["logical_key"] != "CONFIGURED":
        return
    prompts = config.pins.list_pins(snapshot_id)
    prompt = next(
        (
            p
            for p in prompts
            if p["pin_type"] == "LLM_PURPOSE_PROMPT"
            and p["logical_key"] == "DOCUMENT_CANDIDATE_EXTRACTION"
        ),
        None,
    )
    if prompt is None:
        return
    with sessions() as s:
        snapshot = s.get(b.AnalysisSnapshotEntity, str(snapshot_id))
        if snapshot.provenance_json.get("document_input_universe_pinned"):
            return
        links = s.scalars(
            select(d.ProjectVersionDocumentLinkEntity.document_version_id).where(
                d.ProjectVersionDocumentLinkEntity.tenant_id == str(context.tenant_id),
                d.ProjectVersionDocumentLinkEntity.project_version_id
                == snapshot.project_version_id,
            )
        ).all()
    if not links:
        return
    storage = storage or (
        FileObjectStorageAdapter(os.environ["DOCUMENT_OBJECT_STORAGE_ROOT"])
        if os.environ.get("DOCUMENT_OBJECT_STORAGE_ROOT")
        else None
    )
    secrets = secrets or (
        EncryptedFileSecretStore(
            os.environ["LLM_SECRET_STORE_ROOT"],
            os.environ["LLM_SECRET_STORE_KEY"].encode(),
            context.tenant_id,
        )
        if os.environ.get("LLM_SECRET_STORE_ROOT") and os.environ.get("LLM_SECRET_STORE_KEY")
        else None
    )
    if storage is None or secrets is None:
        raise ValueError("CAPABILITY_NOT_CONFIGURED: DOCUMENT_SEMANTIC_EXTRACTION")
    request = LLMRequest(
        project_id=intake.project_id,
        analysis_snapshot_id=snapshot_id,
        operation="structured_output",
        prompt_id=UUID(prompt["object_id"]),
        input_refs=(
            InputReference(
                resource_type="PREPARATION",
                resource_id=intake.project_id,
                version_id=UUID(snapshot.project_version_id),
            ),
        ),
        output_schema=DocumentCandidateExtraction.model_json_schema(),
        max_output_tokens=512,
    )
    policy, preference = PostgresLLMInvocationGovernance(config).load(request)
    if "DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED" not in policy.allowed_triggers.get(
        preference.usage_mode, ()
    ):
        return
    types = []
    with sessions() as s:
        for pin in prompts:
            if pin["pin_type"] != "LLM_FACT_TYPE":
                continue
            version = s.get(m.MetadataVersionEntity, pin["version_id"])
            definition = s.get(m.MetadataDefinitionEntity, pin["object_id"])
            if not version or not definition or version.tenant_id != str(context.tenant_id):
                raise GatewayDenied("CANDIDATE_FACT_TYPE_NOT_GOVERNED")
            binding = version.payload_json.get("structured_intake_binding")
            if binding and getattr(intake, binding["field_path"], None) not in (None, "", (), []):
                continue  # Explicit typed values are not re-inferred by an LLM.
            types.append(definition.code)
    repository = PostgresDocumentIntelligenceRepository(sessions, context)

    class DurableReceipt:
        def enqueue(self, **kwargs):
            return None  # Canonical persisted task is executed synchronously at preparation.

    for version_id in links:
        version = repository.get_document_version(UUID(version_id))
        binary = storage.get(version["storage_ref"])
        if (
            len(binary) != version["size_bytes"]
            or hashlib.sha256(binary).hexdigest() != version["content_hash"]
        ):
            raise ValueError("DOCUMENT_BINARY_INTEGRITY_FAILURE")
        inputs = PinnedDocumentInput(config, repository, snapshot_id, types)
        invocation = enhancement_invocation(config, inputs, secrets, redaction=redaction)
        extractor = DocumentSemanticExtractionService(
            repository,
            invocation,
            request,
            inputs.bind,
            fact_types=types,
            minimum_confidence=policy.candidate_min_confidence,
        )
        service = DocumentParseService(
            repository,
            storage,
            default_native_parsers(),
            DurableReceipt(),
            semantic_extractor=extractor,
        )
        task = service.request_parse(
            document_version_id=UUID(version_id),
            idempotency_key=f"llm-preparation:{snapshot_id}:{version_id}",
            parser_profile_id="native-v1",
        )
        service.process_task(UUID(task["task_id"]))

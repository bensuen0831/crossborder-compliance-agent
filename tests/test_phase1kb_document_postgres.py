import hashlib
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_phase1k_a_configuration_postgres import publish
from test_phase1kb_control_postgres import control as control
from test_phase1kb_selection_postgres import selected as selected
from test_phase1kb_snapshot_postgres import bind_published_prompt

from crossborder_compliance.application.context_services import BusinessFactNormalizationService
from crossborder_compliance.domain.contracts import ProjectIntakeContext
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.document_storage import FileObjectStorageAdapter
from crossborder_compliance.infrastructure.llm_document_inputs import prepare_document_candidates
from crossborder_compliance.infrastructure.llm_snapshot_pins import freeze_llm_configuration
from crossborder_compliance.infrastructure.persistence import context_models as e
from crossborder_compliance.infrastructure.persistence import document_models as d
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.context_repositories import (
    PostgresContextResolutionRepository,
)
from crossborder_compliance.infrastructure.persistence.document_repositories import (
    PostgresDocumentIntelligenceRepository,
)
from crossborder_compliance.infrastructure.persistence.document_snapshot_inputs import (
    pin_intake_document_inputs,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)

pytestmark = pytest.mark.runtime_smoke


def document_frame(f, tmp_path, *, confidence=1.0, bad_trace=False, native=False):
    metadata = PostgresAdminMetadataRepository(f["sf"], f["repo"].context)
    definition = metadata.create_definition(
        kind="BUSINESS_FACT_TYPE", code=uuid4().hex, display_name="Governed test fact"
    )
    publish(
        metadata,
        metadata.create_version(definition_id=UUID(definition["definition_id"]), payload={}),
        True,
    )
    config = f["config"]
    policy_pin = config._saved(f["query"], "LLM_INVOCATION_POLICY")[0]
    publish(
        metadata,
        metadata.create_version(
            definition_id=UUID(policy_pin["object_id"]),
            payload={
                "allowed_triggers": {
                    "STANDARD": ["DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED"],
                    "ENHANCED": ["DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED"],
                },
                "max_models": 3,
                "candidate_fact_type_ids": [definition["definition_id"]],
                "candidate_min_confidence": 0.95,
            },
        ),
        True,
    )
    with f["sf"]() as session:
        original = session.get(b.AnalysisSnapshotEntity, str(f["query"].analysis_snapshot_id))
        version = session.get(b.ProjectVersionEntity, original.project_version_id)
        intake = ProjectIntakeContext.model_validate(dict(version.intake_json, record_version=2))
    draft_id, snapshot_id = uuid4(), uuid4()
    query = f["query"].model_copy(update={"analysis_snapshot_id": snapshot_id})
    with f["sf"]() as session, session.begin():
        session.add(
            b.ProjectVersionEntity(
                project_version_id=str(draft_id),
                tenant_id=str(f["tenant"]),
                project_id=str(intake.project_id),
                version_no=2,
                status="DRAFT",
                intake_json=intake.model_dump(mode="json"),
            )
        )
    prompt = bind_published_prompt(f)
    context = RepositoryContext.user(
        f["tenant"],
        "owner",
        set(config.context.permission.scopes)
        | {"document:read", f"prompt:{prompt['definition_id']}:use"},
    )
    storage = FileObjectStorageAdapter(tmp_path / "objects")
    binary = (
        b"Storage is described in an unstructured requirement paragraph."
        if not native
        else b"Storage: selected location\n"
    )
    ref = storage.put(
        object_key=f"tenant/{f['tenant']}/test/input.txt", content=binary, content_type="text/plain"
    )
    repo = PostgresDocumentIntelligenceRepository(f["sf"], context)
    document = repo.create_document_version(
        project_id=intake.project_id,
        filename="input.txt",
        mime_type="text/plain",
        size_bytes=len(binary),
        content_hash=hashlib.sha256(binary).hexdigest(),
        storage_ref=ref,
    )
    with f["sf"]() as s, s.begin():
        s.add(
            d.ProjectVersionDocumentLinkEntity(
                link_id=str(uuid4()),
                tenant_id=str(f["tenant"]),
                project_version_id=str(draft_id),
                document_version_id=document["document_version_id"],
            )
        )

    with f["sf"]() as s, s.begin():
        s.get(b.ProjectVersionEntity, str(draft_id)).status = "CONFIRMED"
        s.add(
            b.AnalysisSnapshotEntity(
                analysis_snapshot_id=str(snapshot_id),
                tenant_id=str(f["tenant"]),
                project_version_id=str(draft_id),
                snapshot_version="2",
                analysis_as_of_date=intake.analysis_as_of_date,
                provenance_json={"workflow_run_id": str(uuid4())},
            )
        )
    assert freeze_llm_configuration(f["sf"], context, intake, snapshot_id) == "CONFIGURED"

    def output(payload):
        texts = json.loads(payload["messages"][-1]["content"])["source_nodes"]
        node = str(uuid4()) if bad_trace else texts[-1]["source_node_id"]
        return {
            "facts": [
                {
                    "source_node_id": node,
                    "confidence": confidence,
                    "fact_type": definition["code"],
                    "value": "selected location",
                }
            ],
            "items": [
                {
                    "source_node_id": node,
                    "confidence": confidence,
                    "name": "input item",
                    "description": "",
                }
            ],
            "nodes": [
                {"source_node_id": node, "confidence": confidence, "key": "a", "name": "origin"},
                {
                    "source_node_id": node,
                    "confidence": confidence,
                    "key": "b",
                    "name": "destination",
                },
            ],
            "edges": [
                {
                    "source_node_id": node,
                    "confidence": confidence,
                    "source_key": "a",
                    "destination_key": "b",
                }
            ],
        }

    for box in f["outputs"]:
        box[0] = output
    return intake, query, context, storage, repo


def test_real_binary_llm_candidates_genuine_trace_resolution_and_restart(selected, tmp_path):
    f = selected
    intake, query, context, storage, repo = document_frame(f, tmp_path)

    def prepare():
        prepare_document_candidates(
            f["sf"],
            context,
            intake,
            query.analysis_snapshot_id,
            storage=storage,
            secrets=f["store"],
        )

    prepare()
    with f["sf"]() as s:
        pins = s.scalars(
            select(d.AnalysisSnapshotParseRunPinEntity).where(
                d.AnalysisSnapshotParseRunPinEntity.analysis_snapshot_id
                == str(query.analysis_snapshot_id)
            )
        ).all()
        assert len(pins) == 1
        run_id = UUID(pins[0].parse_run_id)
        provenance = s.get(d.DocumentParseRunDetailEntity, str(run_id)).provenance_json
        assert provenance["semantic_invocation"]["authority"] == "DERIVED_CANDIDATE"
        assert (
            s.scalar(
                select(func.count())
                .select_from(e.BusinessFactEntity)
                .where(e.BusinessFactEntity.project_id == str(intake.project_id))
            )
            == 0
        )
        traces = s.scalars(
            select(b.SourceTraceRefEntity).where(
                b.SourceTraceRefEntity.document_version_id == pins[0].document_version_id
            )
        ).all()
        assert traces and all(
            trace.document_version_id == pins[0].document_version_id for trace in traces
        )
    assert len(repo.list_facts(run_id)) == 1 and len(repo.list_candidate_items(run_id)) == 1
    assert len(repo.list_candidate_flows(run_id)["edges"]) == 1
    prepare()  # Completed canonical task creates neither a run nor duplicate candidates.
    assert len(repo.list_facts(run_id)) == 1
    assert pin_intake_document_inputs(
        f["sf"], context, intake.project_id, query.analysis_snapshot_id
    ) == (run_id,)
    resolution = PostgresContextResolutionRepository(f["sf"], context, parse_run_ids=(run_id,))
    facts = BusinessFactNormalizationService(resolution).normalize(intake.project_id, version=1)
    assert len(facts) == 1 and facts[0].validation_status.value == "VALIDATED"
    assert facts[0].source_trace_ids


@pytest.mark.parametrize("invalid", ["low_confidence", "invalid_trace", "unknown_fact_type"])
def test_semantic_uncertainty_cannot_enter_formal_input(selected, tmp_path, invalid):
    f = selected
    intake, query, context, storage, repo = document_frame(
        f,
        tmp_path,
        confidence=0.2 if invalid == "low_confidence" else 1,
        bad_trace=invalid == "invalid_trace",
    )
    if invalid == "unknown_fact_type":
        for box in f["outputs"]:
            original = box[0]

            def unknown(payload, original=original):
                output = original(payload)
                output["facts"][0]["fact_type"] = "NOT_GOVERNED"
                return output

            box[0] = unknown
    prepare_document_candidates(
        f["sf"], context, intake, query.analysis_snapshot_id, storage=storage, secrets=f["store"]
    )
    with pytest.raises(ValueError, match="REVIEW_REQUIRED: DOCUMENT_PARSE_QUALITY"):
        pin_intake_document_inputs(f["sf"], context, intake.project_id, query.analysis_snapshot_id)
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(e.BusinessFactEntity)
                .where(e.BusinessFactEntity.project_id == str(intake.project_id))
            )
            == 0
        )


def test_native_structured_input_does_not_invoke_semantic_model(selected, tmp_path):
    f = selected
    intake, query, context, storage, repo = document_frame(f, tmp_path, native=True)
    prepare_document_candidates(
        f["sf"], context, intake, query.analysis_snapshot_id, storage=storage, secrets=f["store"]
    )
    assert not any(call[1] == "structured_output" for calls in f["calls"] for call in calls)


@pytest.mark.parametrize("selected", ["MULTI_MODEL"], indirect=True)
def test_multi_model_disagreement_uses_existing_fact_conflict_authority(selected, tmp_path):
    f = selected
    intake, query, context, storage, repo = document_frame(f, tmp_path)
    original = f["outputs"][1][0]

    def conflicting(payload):
        output = original(payload)
        output["facts"][0]["value"] = "different location"
        return output

    f["outputs"][1][0] = conflicting
    prepare_document_candidates(
        f["sf"], context, intake, query.analysis_snapshot_id, storage=storage, secrets=f["store"]
    )
    runs = pin_intake_document_inputs(
        f["sf"], context, intake.project_id, query.analysis_snapshot_id
    )
    resolution = PostgresContextResolutionRepository(f["sf"], context, parse_run_ids=runs)
    facts = BusinessFactNormalizationService(resolution).normalize(intake.project_id, version=1)
    assert len(facts) == 2 and all(fact.review_required for fact in facts)
    assert [row["conflict_type"] for row in resolution.list_conflicts(intake.project_id)] == [
        "BUSINESS_FACT_CONFLICT"
    ]

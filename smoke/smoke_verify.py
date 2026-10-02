from __future__ import annotations

import ast
import json
import os
from collections import Counter
from pathlib import Path
from uuid import UUID
from sqlalchemy import inspect, select
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.contracts import WorkflowEventDTO, WorkflowEventType
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity, AuditEventEntity, ReviewTaskEntity,
    WorkflowEventEntity, WorkflowRunEntity,
)
from crossborder_compliance.workflows.state import STATE_SCHEMA_VERSION
from smoke.evidence_utils import write_json, write_markdown

STATE_FILE = Path(os.getenv("SMOKE_STATE_FILE", "/tmp/phase1a_smoke_ids.json"))
RAW_LANGGRAPH_KEYS = {
    "__interrupt__", "checkpoint_id", "checkpoint_ns", "langgraph_step",
    "langgraph_node", "tasks", "next",
}

def _external_contract_is_canonical_only() -> bool:
    fields = set(WorkflowEventDTO.model_fields)
    return fields.isdisjoint(RAW_LANGGRAPH_KEYS) and "event_type" in fields and "workflow_run_id" in fields

def _api_layer_has_no_raw_langgraph_import() -> bool:
    root = Path(__file__).resolve().parents[1] / "src" / "crossborder_compliance" / "interfaces"
    forbidden_runtime_symbols = {"checkpoint_writes", "checkpoint_blobs", "checkpoints"}
    for path in root.rglob("*.py"):
        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == "langgraph" or alias.name.startswith("langgraph.") for alias in node.names):
                    return False
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "langgraph" or module.startswith("langgraph."):
                    return False
        lowered = source.lower()
        if any(symbol in lowered for symbol in forbidden_runtime_symbols):
            return False
    return True

def main() -> None:
    ids = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    workflow_run_id = UUID(ids["workflow_run_id"])
    settings = get_settings()
    engine, session_factory = build_session_factory(settings.database_url)

    with session_factory() as db:
        run = db.get(WorkflowRunEntity, str(workflow_run_id))
        snapshot = db.get(AnalysisSnapshotEntity, ids["analysis_snapshot_id"])
        reviews = list(db.scalars(select(ReviewTaskEntity).where(
            ReviewTaskEntity.workflow_run_id == str(workflow_run_id))))
        audits = list(db.scalars(select(AuditEventEntity).where(
            AuditEventEntity.workflow_run_id == str(workflow_run_id))))
        event_rows = list(db.scalars(
            select(WorkflowEventEntity)
            .where(WorkflowEventEntity.workflow_run_id == str(workflow_run_id))
            .order_by(WorkflowEventEntity.occurred_at)
        ))

    canonical = {e.value for e in WorkflowEventType}
    events = [e.event_type for e in event_rows]
    counts = Counter(events)
    domain_metadata_tables = set(inspect(engine).get_table_names())
    raw_payload_key_hits = sorted({
        key for row in event_rows for key in (row.payload_json or {}).keys()
        if key in RAW_LANGGRAPH_KEYS
    })

    checkpoint_tables: list[str] = []
    checkpoint_row_count = 0
    checkpoint_error: str | None = None
    try:
        import psycopg
        with psycopg.connect(settings.langgraph_database_uri) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema=current_schema() AND table_name LIKE 'checkpoint%' "
                    "ORDER BY table_name"
                )
                checkpoint_tables = [r[0] for r in cur.fetchall()]
                if "checkpoints" in checkpoint_tables:
                    cur.execute("SELECT count(*) FROM checkpoints WHERE thread_id=%s", (str(workflow_run_id),))
                    checkpoint_row_count = int(cur.fetchone()[0])
    except Exception as exc:
        checkpoint_error = f"{type(exc).__name__}: {exc}"

    run_versions_retained = bool(
        run
        and run.graph_definition_version == ids["graph_definition_version"]
        and run.langgraph_runtime_version == ids["langgraph_runtime_version"]
        and run.checkpointer_version == ids["checkpointer_version"]
        and run.state_schema_version == ids["state_schema_version"] == STATE_SCHEMA_VERSION
    )
    tenant_preserved = bool(
        run
        and run.tenant_id == ids["tenant_id"]
        and all(r.tenant_id == ids["tenant_id"] for r in reviews)
        and all(e.tenant_id == ids["tenant_id"] for e in event_rows)
    )
    snapshot_preserved = bool(
        run
        and run.analysis_snapshot_id == ids["analysis_snapshot_id"]
        and snapshot is not None
        and ids.get("process2_checkpoint_context_preserved") is True
    )
    canonical_only = all(e in canonical for e in events)
    completion_audit_count = sum(1 for a in audits if a.event_type == "WORKFLOW_COMPLETED")

    assertions: dict[str, bool] = {
        "postgres_checkpoint_row_gt_zero": checkpoint_row_count > 0,
        "workflow_run_exists": run is not None,
        "analysis_snapshot_exists": snapshot is not None,
        "analysis_snapshot_and_checkpoint_are_separate_sources": bool(
            snapshot is not None and checkpoint_row_count > 0
            and "analysis_snapshots" in domain_metadata_tables
            and "checkpoints" in checkpoint_tables
        ),
        "workflow_run_id_equals_thread_id": bool(
            run is not None and run.workflow_run_id == run.thread_id == ids["workflow_run_id"]
        ),
        "review_task_count_eq_one": len(reviews) == 1,
        "review_required_event_count_eq_one": counts[WorkflowEventType.REVIEW_REQUIRED.value] == 1,
        "workflow_resumed_event_count_eq_one": counts[WorkflowEventType.WORKFLOW_RESUMED.value] == 1,
        "workflow_completed_event_count_eq_one": counts[WorkflowEventType.WORKFLOW_COMPLETED.value] == 1,
        "formal_completion_audit_count_eq_one": completion_audit_count == 1,
        "final_workflow_status_completed": bool(run is not None and run.status == "COMPLETED"),
        "tenant_id_preserved_after_restart": tenant_preserved,
        "analysis_snapshot_id_preserved_after_restart": snapshot_preserved,
        "graph_runtime_checkpointer_state_schema_versions_retained": run_versions_retained,
        "audit_provenance_retained": len(audits) >= 2 and all(bool(a.provenance_json) for a in audits),
        "canonical_events_only": canonical_only,
        "no_raw_langgraph_payload_keys_persisted": not raw_payload_key_hits,
        "external_workflow_event_contract_has_no_raw_langgraph_fields": _external_contract_is_canonical_only(),
        "api_layer_has_no_raw_langgraph_import": _api_layer_has_no_raw_langgraph_import(),
        "domain_metadata_does_not_own_checkpoint_tables": "checkpoints" not in {*AnalysisSnapshotEntity.metadata.tables.keys()},
        "process1_checkpoint_existed_before_process_exit": int(ids.get("process1_checkpoint_row_count", 0)) > 0,
        "process2_loaded_checkpoint_context_before_resume": ids.get("process2_checkpoint_context_preserved") is True,
        "resume_retry_safe": ids.get("resume_retry_safe") is True,
        "resume_retry_event_counts_unchanged": ids.get("resume_retry_event_counts_unchanged") is True,
        "resume_retry_review_count_unchanged": ids.get("resume_retry_review_count_unchanged") is True,
    }

    result = {
        "assertions": assertions,
        "all_mandatory_assertions_pass": all(assertions.values()),
        "workflow_run_id": ids["workflow_run_id"],
        "thread_id": run.thread_id if run else None,
        "tenant_id": ids["tenant_id"],
        "analysis_snapshot_id": ids["analysis_snapshot_id"],
        "workflow_status": run.status if run else None,
        "canonical_events": events,
        "canonical_event_counts": dict(counts),
        "review_task_count": len(reviews),
        "audit_event_count": len(audits),
        "completion_audit_count": completion_audit_count,
        "checkpoint_tables": checkpoint_tables,
        "checkpoint_row_count": checkpoint_row_count,
        "checkpoint_query_error": checkpoint_error,
        "raw_payload_key_hits": raw_payload_key_hits,
        "retained_versions": {
            "graph_definition_version": run.graph_definition_version if run else None,
            "langgraph_runtime_version": run.langgraph_runtime_version if run else None,
            "checkpointer_version": run.checkpointer_version if run else None,
            "state_schema_version": run.state_schema_version if run else None,
        },
        "process1_checkpoint_next": ids.get("process1_checkpoint_next"),
        "process2_checkpoint_values_before_resume": ids.get("process2_checkpoint_values_before_resume"),
    }
    write_json("runtime_assertions.json", result)

    assertion_table = "\n".join(
        ["| Mandatory assertion | Result |", "|---|---|"]
        + [f"| `{name}` | **{'PASS' if passed else 'FAIL'}** |" for name, passed in assertions.items()]
    )
    write_markdown(
        "runtime_smoke_result.md",
        "Phase 1A.1 Mandatory PostgreSQL-backed LangGraph Runtime Smoke",
        [
            ("Gate Decision", "**PASS**" if result["all_mandatory_assertions_pass"] else "**FAIL**"),
            ("Mandatory Assertions", assertion_table),
            ("Workflow Identity", f"- workflow_run_id: `{ids['workflow_run_id']}`\n- thread_id: `{run.thread_id if run else 'MISSING'}`\n- tenant_id: `{ids['tenant_id']}`\n- analysis_snapshot_id: `{ids['analysis_snapshot_id']}`"),
            ("Checkpoint Evidence", f"- tables: `{checkpoint_tables}`\n- rows for thread: `{checkpoint_row_count}`\n- process-1 rows before exit: `{ids.get('process1_checkpoint_row_count')}`"),
            ("Resume Retry", f"- safe: `{ids.get('resume_retry_safe')}`\n- events unchanged: `{ids.get('resume_retry_event_counts_unchanged')}`\n- review count unchanged: `{ids.get('resume_retry_review_count_unchanged')}`"),
        ],
    )

    event_rows_md = "\n".join(
        ["| # | Event | Node | Tenant | Payload |", "|---:|---|---|---|---|"]
        + [f"| {i} | `{row.event_type}` | `{row.node_code or ''}` | `{row.tenant_id}` | `{json.dumps(row.payload_json, sort_keys=True)}` |"
           for i, row in enumerate(event_rows, start=1)]
    )
    write_markdown(
        "runtime_event_evidence.md",
        "Phase 1A.1 Runtime Event Evidence",
        [
            ("Canonical Event Sequence", event_rows_md),
            ("Counts", f"~~~json\n{json.dumps(dict(counts), indent=2, sort_keys=True)}\n~~~"),
            ("Raw LangGraph Boundary", f"- persisted raw-key hits: `{raw_payload_key_hits}`\n- public DTO raw fields: `none` = `{_external_contract_is_canonical_only()}`\n- API layer imports raw LangGraph/checkpointer internals: `{not _api_layer_has_no_raw_langgraph_import()}`"),
        ],
    )

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    raise SystemExit(0 if result["all_mandatory_assertions_pass"] else 2)

if __name__ == "__main__":
    main()

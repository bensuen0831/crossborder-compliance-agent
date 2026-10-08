"""Additive review ownership boundaries; existing permanent rules are unchanged."""

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.m2d_ownership import overlay


def check(root):
    root = Path(root)
    src = root / "src/crossborder_compliance"
    app = (src / "application/review_services.py").read_text()
    repo = (src / "infrastructure/persistence/review_governance.py").read_text()
    graph = (src / "workflows/canonical.py").read_text()
    matrix = (src / "domain/review_governance.py").read_text()
    owner = (src / "infrastructure/persistence/project_intake.py").read_text()
    mig = (root / "alembic/versions/0015_m2d_review_governance.py").read_text()
    ui_path = root / "frontend/src/features/reviews/ReviewCenter.tsx"
    ui = ui_path.read_text() if ui_path.exists() else ""
    models = (src / "infrastructure/persistence/review_models.py").read_text()
    table_names = [
        n.value.value
        for p in (src / "infrastructure/persistence").glob("*.py")
        for n in ast.walk(ast.parse(p.read_text()))
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in n.targets)
        and isinstance(n.value, ast.Constant)
        and isinstance(n.value.value, str)
    ]
    tree = ast.parse(app)
    request_cls = [
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ReviewDecisionRequest"
    ][0]
    fields = {n.target.id for n in request_cls.body if isinstance(n, ast.AnnAssign)}
    decide = (
        ast.get_source_segment(
            app,
            [
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef)
                and n.name == "decide"
                and n.body
                and not isinstance(n.body[0], ast.Expr)
            ][0],
        )
        or ""
    )
    valid, paths, source = overlay(root)
    checks = {
        "review_task_reuses_canonical_authority": "b.ReviewTaskEntity" in repo
        and "ReviewTaskEntity" not in models,
        "review_decision_is_append_only": "b.ReviewDecisionEntity(" in repo
        and "BEFORE UPDATE OR DELETE" in mig,
        "frontend_cannot_set_decided_by": "decided_by" not in fields
        and "self._context.permission.actor_id" in repo,
        "frontend_cannot_patch_formal_results": "PATCH_FINAL_PATH" not in app
        and all(x not in ui for x in ("PATCH_FINAL_PATH", "risk_score:", "final_path:")),
        "allowed_actions_are_backend_owned": "resolution_actions(" in repo
        and "allowed_actions.includes" in ui,
        "approve_cannot_fabricate_missing_fact": "BUSINESS_FACT_CONFLICT" in matrix
        and "APPROVE" in matrix
        and "requirement_confirmation" in matrix,
        "approve_cannot_fabricate_evidence": "EVIDENCE_INSUFFICIENT" in matrix
        and "ACTION_NOT_ALLOWED" in repo,
        "request_changes_does_not_resume": "decision.decision == ReviewDecisionCode.APPROVE"
        in decide,
        "correction_routes_to_owning_domain": "owner.successor_from_review(" in repo
        and "ProjectIntakeService(owner, prepared).confirm(" in repo,
        "input_correction_cannot_mutate_snapshot": "source_snapshot_id=" in repo
        and "facts.analysis_as_of_date" in owner,
        "successor_snapshot_required_for_input_change": 'uuid5(successor.project_version_id, "analysis-snapshot")'
        in repo,
        "same_snapshot_resume_requires_no_input_mutation": 'value.resolution_mode != "SAME_SNAPSHOT"'
        in app,
        "review_resume_reexecutes_owner": "goto=state.current_step.value" in graph
        and "authorize_resume" in app,
        "no_arbitrary_graph_jump": "start_at" not in fields and 'Literal["requirement"]' in app,
        "reexecution_boundary_is_backend_owned": '"rerun_from_stage": "requirement"' in repo,
        "historical_result_remains_immutable": valid
        and source is not None
        and "HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED" in matrix,
        "review_lineage_is_auditable": "ReviewCorrectionEntity" in repo
        and "REVIEW_SUCCESSOR_CREATED" in repo
        and "BEFORE UPDATE OR DELETE" in mig,
        "single_workflow_runtime": sum(
            p.read_text().count("StateGraph(")
            for p in (src / "workflows").glob("*.py")
            if p.name != "langgraph_adapter.py"
        )
        == 1,
        "single_checkpointer": "PostgresSaver(" not in app + repo
        and "from_conn_string" not in app + repo,
        "single_review_authority": table_names.count("review_tasks") == 1
        and table_names.count("review_decisions") == 1,
        "stage2_not_started": all(
            x not in app + repo + ui
            for x in ("generate_document(", "Stage2Workflow", "generate_scc(")
        ),
    }
    return dict(
        pass_=all(checks.values()),
        passed=sum(checks.values()),
        total=len(checks),
        checks=checks,
        ownership_paths=len(paths),
    )


if __name__ == "__main__":
    result = check(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(not result["pass_"])

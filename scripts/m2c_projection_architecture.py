"""Additive C1 read/projection boundaries; no changes to permanent rules."""

import ast
import json
from pathlib import Path


def check(root):
    root = Path(root)
    src = root / "src/crossborder_compliance"
    application = (src / "application/stage1_result.py").read_text()
    workflow = (src / "application/workflow_formal.py").read_text()
    graph = (src / "workflows/canonical.py").read_text()
    enum = (src / "application/workflow_skeleton.py").read_text()
    persistence = (src / "infrastructure/persistence/workflow_read_projection.py").read_text()
    ui = (root / "frontend/src/features/results/Stage1Workspace.tsx").read_text()
    transport = (root / "frontend/src/features/results/api.ts").read_text()
    imports = [
        n.module or "" for n in ast.walk(ast.parse(application)) if isinstance(n, ast.ImportFrom)
    ]
    checks = {
        "single_canonical_graph": graph.count("StateGraph(") == 1
        and sum(
            p.read_text().count("StateGraph(")
            for p in (src / "workflows").glob("*.py")
            if p.name != "langgraph_adapter.py"
        )
        == 1,
        "formal_order": enum.index("OBLIGATION =")
        < enum.index("CROSS_BORDER =")
        < enum.index("CANDIDATE_PATH =")
        < enum.index("FINAL_PATH =")
        < enum.index("DOCUMENTS ="),
        "nodes_delegate_authority": all(
            x in workflow
            for x in ("self.cross_border", "self.document_requirements", "FormalAuthorityRequest(")
        )
        and "cross_border_assessment(" not in workflow,
        "legacy_version_closed": all(
            x in graph
            for x in (
                "LEGACY_GRAPH_VERSION",
                "LEGACY_STATE_VERSION",
                "LEGACY_NEXT",
                "WORKFLOW_VERSION_MISMATCH",
            )
        ),
        "typed_aggregation_has_no_infrastructure": not any(".infrastructure" in i for i in imports),
        "aggregation_reads_owning_results": all(
            x in application
            for x in (
                "self.decisions.read",
                "self.cross_border.read",
                "self.documents.read",
                "self.country.read",
            )
        )
        and ".execute(" not in application,
        "exact_document_universe": all(
            x in persistence
            for x in ("AnalysisSnapshotParseRunPinEntity", "parse_run_id", "document_version_id")
        ),
        "exact_context_membership": all(
            x in persistence
            for x in (
                "pin.data_inventory_version",
                "pin.data_flow_version",
                "context_resolution_run_id",
            )
        ),
        "result_scope_revalidated": all(
            x in application
            for x in (
                "formal result scope mismatch",
                "formal result subject mismatch",
                "formal result context version mismatch",
            )
        ),
        "historical_authority_gap_explicit": "HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED"
        in application,
        "frontend_uses_authority_not_path_status": "r.cross_border?.items[0]" in ui
        and "final.status ===" not in ui
        and "final.status ==" not in ui,
        "frontend_requires_no_decision_write": "method: 'POST'" not in transport
        and "request<Stage1Result>" in transport,
        "unassessed_subjects_fail_closed": "r.cross_border?.data_item_ids.includes(id)" in ui
        and "r.document_requirements?.data_item_ids.includes(id)" in ui,
        "template_does_not_change_requirement": "code(d.requirement_level)" in ui
        and "d.template_version_id" in ui,
        "stage2_unavailable_and_opt_in_only": "generation_available: Literal[False]" in application
        and "setDocumentSelection(true)" in ui,
    }
    return dict(
        pass_=all(checks.values()), passed=sum(checks.values()), total=len(checks), checks=checks
    )


if __name__ == "__main__":
    result = check(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(not result["pass_"])

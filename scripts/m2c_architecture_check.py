"""Additive C0 boundaries; permanent architecture rules and J owners stay frozen."""

import ast
import json
from pathlib import Path


class Source(str):
    """Ignore formatting; inspect the same approved structural markers."""

    def __contains__(self, token):
        def compact(value):
            return "".join(value.split()).replace("'", "").replace('"', "")

        return compact(token) in compact(str(self))


def check(root):
    root = Path(root)
    src = root / "src/crossborder_compliance"
    engine = (src / "domain/formal_result_engine.py").read_text()
    tree = ast.parse(engine)
    functions = {
        n.name: Source(ast.get_source_segment(engine, n))
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
    }
    services = (src / "application/formal_result_services.py").read_text()
    contracts = (src / "domain/formal_result_contracts.py").read_text()
    policy = (src / "domain/formal_result_policies.py").read_text()
    repo = Source((src / "infrastructure/persistence/formal_result_repository.py").read_text())
    migration = (root / "alembic/versions/0014_m2c_formal_result_authority.py").read_text()
    frontend = "\n".join(p.read_text() for p in (root / "frontend/src").rglob("*.tsx"))
    imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    cross = functions["cross_border_assessment"]
    docs = functions["regulatory_document_requirements"]
    checks = {
        "crossborder_status_not_derived_from_final_path_status": "final_path" not in cross,
        "conditional_proposal_not_equal_conditional_transfer": "CONDITIONAL_PROPOSAL" not in engine,
        "crossborder_has_formal_owner": "class CrossBorderAssessmentService" in services
        and "condition_result" in cross
        and not any(".infrastructure" in x for x in imports),
        "crossborder_policy_is_versioned_and_pinned": all(
            x in repo
            for x in (
                "load_policy",
                "AdminPublishRecordEntity",
                "effective(cfg,when)",
                "PHASE1J_INITIALIZATION",
            )
        ),
        "crossborder_has_legal_basis_and_evidence": (
            "support.legal_basis_ids and support.evidence_ids" in cross
        )
        and "transfer conclusion lacks exact formal support" in contracts,
        "required_document_has_formal_owner": "class RegulatoryDocumentRequirementService"
        in services,
        "required_document_has_requirement_level": all(
            x in policy for x in ("REQUIRED", "CONDITIONAL", "RECOMMENDED", "NOT_APPLICABLE")
        )
        and "requirement_level: RequirementLevel" in contracts,
        "required_document_is_metadata_rule_driven": "policy.config.entries" in docs
        and "condition_result(entry.condition,x)" in docs,
        "template_availability_does_not_change_legal_requirement": (
            "level=entry.requirement_level if triggered else 'NOT_APPLICABLE'" in docs
        )
        and "template_version_id=template" in docs,
        "required_document_does_not_trigger_generation": all(
            x not in docs for x in ("generate(", "llm", "TemplateGeneration")
        ),
        "stage2_requires_user_opt_in": "Stage2" in (root / "docs/m2c/M2C0_design.md").read_text()
        and "generation" not in services,
        "frontend_has_no_crossborder_decision_logic": all(
            x not in frontend
            for x in (
                "CONDITIONAL_PROPOSAL' ? 'CONDITIONAL_TRANSFER_ALLOWED",
                "function cross_border_assessment",
            )
        ),
        "frontend_has_no_document_requirement_logic": "function regulatory_document_requirements"
        not in frontend,
        "historical_snapshot_preserves_crossborder_result": (
            "result_digest(saved)!=result_digest(current)" in repo
        )
        and "immutable C0 snapshot pin" in migration,
        "historical_snapshot_preserves_document_requirement": "PHASE1C0_TEMPLATE" in migration
        and "immutable pinned template version" in migration
        and "historical=True" in repo,
    }
    return dict(
        pass_=all(checks.values()), passed=sum(checks.values()), total=len(checks), checks=checks
    )


if __name__ == "__main__":
    result = check(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(not result["pass_"])

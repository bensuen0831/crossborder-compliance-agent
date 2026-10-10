"""Additive Phase1H/M2-A owning recovery checks; no permanent rule edits."""

import ast
import json
from pathlib import Path


def method(source, name):
    node = next(
        n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.get_source_segment(source, node)


def check(root):
    root = Path(root)
    base = root / "src/crossborder_compliance"
    repo = (base / "infrastructure/persistence/classification_repository.py").read_text()
    batch, runtime = method(repo, "pin_configurations"), method(repo, "_prepare")
    # Explicit binding branch must precede the isolated legacy-only fallback.
    explicit = runtime.split("if binding_pins:")[1].split("else:")[0]
    stages = (base / "application/workflow_formal.py").read_text()
    app = (base / "domain/regulation_applicability.py").read_text()
    governance = (base / "infrastructure/persistence/classification_governance.py").read_text()
    domain = (base / "domain/classification.py").read_text()
    model = (base / "infrastructure/persistence/metadata_models.py").read_text()
    rules = (base / "infrastructure/persistence/rule_governance.py").read_text()
    mig = (
        root / "alembic/versions/0018_phase1h_multijurisdiction_classification_identity.py"
    ).read_text()
    checks = {
        "classification_execution_has_explicit_jurisdiction": "jurisdiction_id=jurisdiction_id"
        in repo
        and "jurisdiction_id: UUID" in domain,
        "multi_jurisdiction_snapshot_has_explicit_classification_bindings": (
            "classification_bindings:" in stages
        )
        and "pin_configurations(" in (base / "infrastructure/intake_composition.py").read_text(),
        "classification_runtime_does_not_infer_jurisdiction_from_context_intersection": (
            "jurisdiction_id is None" in explicit
        )
        and "jurisdiction = UUID(str(jurisdiction_id))" in explicit
        and "scheme.jurisdiction_ids" not in explicit,
        "single_active_scheme_invariant_preserved": "if len(versions) != 1:" in batch,
        "classification_binding_is_governed": "ClassificationBindingEntity" in governance
        and "AdminPublishRecordEntity" in batch
        and 'ClassificationBindingEntity.status == "ACTIVE"' in batch
        and "effective(row)" in batch
        and "rule jurisdiction" in rules,
        "classification_binding_is_snapshot_frozen": "CLASSIFICATION_BINDING_V1" in batch
        and "logical_key=str(binding.jurisdiction_id)" in batch
        and "AnalysisSnapshotRegistryPinEntity" in model,
        "rule_pins_cover_all_pinned_classification_jurisdictions": "for j in jurisdictions" in batch
        and "for rule in rules:" in batch
        and "RULE_V1" in batch
        and "with self.sessions() as s, s.begin():" in batch,
        "classification_result_is_jurisdiction_scoped": "jurisdiction_id: UUID" in domain
        and "ClassificationResultEntity.jurisdiction_id == str(result.jurisdiction_id)" in repo
        and '"jurisdiction_id"' in mig
        and "formal_provenance_json IS NOT NULL" in mig,
        "applicability_consumes_same_jurisdiction_classification": (
            "result.jurisdiction_id == binding.jurisdiction_id" in stages
        )
        and "for ident in scoped_classes" in stages,
        "cross_jurisdiction_rule_hit_leakage_forbidden": "wrong RuleHit jurisdiction" in app
        and "classification mixed jurisdiction RuleHits" in repo,
        "historical_classification_does_not_reresolve_active_binding": batch.index("if existing:")
        < batch.index("ClassificationSchemeVersionEntity.lifecycle_status")
        and "ClassificationBindingEntity" not in runtime
        and 'if p.pin_type == "RULE_V1"' in runtime,
    }
    return {
        "total": len(checks),
        "passed": sum(checks.values()),
        "pass_": all(checks.values()),
        "checks": checks,
    }


if __name__ == "__main__":
    result = check(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass_"] else 1)

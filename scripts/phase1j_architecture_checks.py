"""Executable Rules152–155 checks; earlier architecture checks remain intact."""

import ast
import subprocess
from pathlib import Path


def check(root):
    from decimal import Decimal

    from crossborder_compliance.application.decision_services import PARENTS, DecisionRequest
    from crossborder_compliance.domain.decision_contracts import (
        Action,
        FinalCompliancePathDTOv2,
        LegalSupport,
        canonical_json,
    )
    from crossborder_compliance.domain.decision_policies import POLICY_TYPES
    from crossborder_compliance.infrastructure.persistence.decision_models import (
        PARENTS as SQL_PARENTS,
    )
    from crossborder_compliance.infrastructure.persistence.decision_models import TABLES
    from scripts.phase1j_ownership import BASE

    root = Path(root)
    src = root / "src/crossborder_compliance"
    paths = [
        *sorted((src / "domain").glob("decision_*.py")),
        src / "application/decision_services.py",
    ]
    sources = [p.read_text() for p in paths]
    imports = [
        n.module or ""
        for s in sources
        for n in ast.walk(ast.parse(s))
        if isinstance(n, ast.ImportFrom)
    ]
    imports += [
        a.name
        for s in sources
        for n in ast.walk(ast.parse(s))
        if isinstance(n, ast.Import)
        for a in n.names
    ]
    engine = (src / "domain/decision_engine.py").read_text()
    functions = {
        n.name: ast.get_source_segment(engine, n)
        for n in ast.parse(engine).body
        if isinstance(n, ast.FunctionDef)
    }
    risk = (src / "domain/decision_risk.py").read_text()
    policies = (src / "domain/decision_policies.py").read_text()
    repository = (src / "infrastructure/persistence/decision_repository.py").read_text()
    migration = (root / "alembic/versions/0010_phase1j_formal_decisions.py").read_text()
    baseline = subprocess.check_output(["git", "show", BASE + ":ARCHITECTURE_RULES.md"], cwd=root)
    rules = (root / "ARCHITECTURE_RULES.md").read_bytes()
    expected = {
        "OBLIGATION": (),
        "CANDIDATE_PATH": ("OBLIGATION",),
        "RISK": ("CANDIDATE_PATH",),
        "RECOMMENDATION": ("CANDIDATE_PATH", "RISK"),
        "FINAL_PATH": ("OBLIGATION", "CANDIDATE_PATH", "RISK", "RECOMMENDATION"),
    }
    return {
        "j_approved_rules_append_only": rules.startswith(baseline)
        and len([l for l in rules[len(baseline) :].decode().splitlines() if l[:3].isdigit()]) == 4
        and all(str(i) + "." in rules[len(baseline) :].decode() for i in range(152, 156)),
        "j_v1_contracts_byte_preserved": (src / "domain/contracts.py").read_bytes()
        == subprocess.check_output(
            ["git", "show", BASE + ":src/crossborder_compliance/domain/contracts.py"], cwd=root
        ),
        "j_dependency_order_authority": PARENTS == SQL_PARENTS == expected,
        "j_domain_application_pure": not any(
            i.split(".")[0]
            in {
                "sqlalchemy",
                "psycopg",
                "redis",
                "langgraph",
                "requests",
                "httpx",
                "openai",
                "subprocess",
            }
            or ".infrastructure" in i
            for i in imports
        ),
        "j_no_llm_authority": not any("llm_gateway" in i or "agents" in i for i in imports),
        "j_legal_stage_excludes_future_risk": all(
            "risk" not in functions[n].lower() and "recommendation" not in functions[n].lower()
            for n in ("obligations", "candidates")
        ),
        "j_decimal_risk_governed_examples": "Decimal" in risk
        and "quantize" in risk
        and "float(" not in risk
        and all(
            x in policies
            for x in ("persisted risk example failed", "without gaps/overlaps", "sum exactly1")
        ),
        "j_recommendation_no_tie_choice": all(
            x in functions["recommendation"]
            for x in (
                "len(tied) > 1",
                '"TIED"',
                '"INCOMPARABLE_RISK"',
                'selected, review = "NO_RECOMMENDATION", None, True',
            )
        ),
        "j_final_preserves_unresolved": all(
            x in functions["final_path"]
            for x in (
                "if unresolved:",
                "selected = None",
                '"CONDITIONAL_PROPOSAL"',
                "unmet_requirement_ids",
            )
        )
        and "APPROVED" not in str(FinalCompliancePathDTOv2.model_fields["status"].annotation)
        and str(Action.model_fields["performed"].annotation) == "typing.Literal[False]",
        "j_reference_only_request": set(DecisionRequest.model_fields)
        == {
            "project_id",
            "analysis_snapshot_id",
            "subject_type",
            "subject_id",
            "stage_kind",
            "applicability_result_ids",
            "upstream_refs",
            "idempotency_key",
        }
        and DecisionRequest.model_config.get("extra") == "forbid",
        "j_existing_registry_policy_governance": set(POLICY_TYPES)
        == {"OBLIGATION_POLICY", "COMPLIANCE_PATH_POLICY", "RISK_POLICY", "RECOMMENDATION_POLICY"}
        and all(
            x in repository
            for x in (
                "AnalysisSnapshotRegistryPinEntity",
                "AdminPublishRecordEntity",
                "PHASE1J_DEPENDENCY",
                "permission_scopes",
            )
        ),
        "j_five_immutable_result_authorities": len(TABLES) == 5
        and all(
            x in migration
            for x in (
                "CREATE TRIGGER tr_j_immutable",
                "phase1j_applicability_scope",
                "phase1j_request_scope",
                "archive/export",
            )
        )
        and 'down_revision = "0009_phase1i"' in migration
        and "Base.metadata" not in migration,
        "j_canonical_provenance_refs": {
            "citation_ids",
            "legal_basis_ids",
            "evidence_ids",
            "rule_hit_ids",
            "applicability_result_ids",
            "knowledge_version_ids",
            "structure_node_ids",
        }
        <= LegalSupport.model_fields.keys(),
        "j_locale_neutral_canonical_decimal": canonical_json({"v": Decimal("1.00")})
        == canonical_json({"v": Decimal(1)})
        and not any(any("\u3400" <= c <= "\u9fff" for c in s) for s in sources)
        and 'pop("localized_display", None)' in engine,
        "j_security_idempotency_revalidation": all(
            x in repository
            for x in (
                "owner_actor_id",
                "idempotency key fingerprint mismatch",
                "authorized computation",
                "saved decision no longer revalidates",
                "pg_advisory_xact_lock",
            )
        ),
        "j_migration_dual_path_test": (root / "tests/test_phase1j_migrations.py").exists()
        and all(
            x in (root / "tests/test_phase1j_migrations.py").read_text()
            for x in (
                "git",
                "archive",
                "catalog(urls[0]) == catalog(urls[1])",
                "empty_roundtrip",
                "transactional_refusal",
            )
        ),
    }

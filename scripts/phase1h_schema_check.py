"""Measured Phase 1H assertions on canonical PostgreSQL rule/classification extensions."""

import json
import os
from pathlib import Path

from sqlalchemy import inspect, text

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_engine
from crossborder_compliance.infrastructure.persistence.migration_lineage import revision_at_or_after


def main():
    engine = build_engine(get_settings().database_url)
    ins = inspect(engine)

    def columns(table):
        return {value["name"] for value in ins.get_columns(table)}

    def checks(table):
        return {value["name"] for value in ins.get_check_constraints(table)}

    def indexes(table):
        return {value["name"] for value in ins.get_indexes(table)}

    with engine.connect() as conn:
        revision = conn.scalar(text("SELECT version_num FROM alembic_version"))
        triggers = set(
            conn.scalars(
                text(
                    "SELECT DISTINCT trigger_name FROM information_schema.triggers WHERE "
                    "trigger_schema='public'"
                )
            )
        )
    results = {
        "phase1h_lineage": revision_at_or_after(revision, "0008_phase1h"),
        "no_duplicate_rule_or_classification_store": not {
            "formal_classifications",
            "safe_rule_versions",
            "formal_rule_hits",
        }
        & set(ins.get_table_names()),
        "canonical_rule_contract": "runtime_contract_json" in columns("rule_versions"),
        "canonical_rule_governance": "governance_json" in columns("rule_versions"),
        "canonical_rulehit_provenance": "formal_provenance_json" in columns("rule_hits"),
        "canonical_classification_provenance": "formal_provenance_json"
        in columns("classification_results"),
        "classification_project_pin": "project_id" in columns("classification_results"),
        "classification_snapshot_pin": "analysis_snapshot_id" in columns("classification_results"),
        "rule_effective_dates_constraint": "ck_rule_effective_interval" in checks("rule_versions"),
        "scheme_effective_dates_constraint": "ck_scheme_effective_interval"
        in checks("classification_scheme_versions"),
        "active_rule_requires_validated_review": "ck_rule_v1_active_gate"
        in checks("rule_versions"),
        "formal_result_requires_scope": "ck_formal_classification_scope"
        in checks("classification_results"),
        "rule_runtime_index": "ix_rule_runtime_scope" in indexes("rule_versions"),
        "formal_result_snapshot_index": "ix_formal_classification_snapshot"
        in indexes("classification_results"),
        "formal_result_retry_unique": "uq_formal_classification_snapshot"
        in indexes("classification_results"),
        "immutable_rule_payload": "phase1h_rule_immutable" in triggers,
        "immutable_rule_tests": "phase1h_rule_tests_immutable" in triggers,
        "immutable_scheme_content": "phase1h_scheme_immutable" in triggers,
        "immutable_formal_result": "phase1h_classification_immutable" in triggers,
        "immutable_rulehit": "phase1h_rulehit_immutable" in triggers,
    }
    result = {
        "pass": all(results.values()),
        "passed": sum(results.values()),
        "total": len(results),
        "checks": results,
    }
    print(json.dumps(result, indent=2))
    if directory := os.getenv("EVIDENCE_DIR"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        (Path(directory) / "phase1h_schema_check.json").write_text(json.dumps(result, indent=2))
    engine.dispose()
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()

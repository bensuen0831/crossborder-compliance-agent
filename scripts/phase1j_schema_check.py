"""Measured schema assertions for the five formal authorities and scoped links."""

import json
import os
from pathlib import Path

from sqlalchemy import inspect, text

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_engine
from crossborder_compliance.infrastructure.persistence.decision_models import PARENTS, SCOPE, TABLES
from crossborder_compliance.infrastructure.persistence.migration_lineage import revision_at_or_after


def main():
    engine = build_engine(get_settings().database_url)
    ins = inspect(engine)
    with engine.connect() as conn:
        revision = conn.scalar(text("SELECT version_num FROM alembic_version"))
        triggers = set(
            conn.execute(
                text(
                    "SELECT event_object_table,trigger_name FROM information_schema.triggers WHERE trigger_schema='public'"
                )
            )
        )
    checks = {"phase1j_lineage": revision_at_or_after(revision, "0010_phase1j")}
    for kind, table in TABLES.items():
        columns = {c["name"]: c for c in ins.get_columns(table)}
        fks = ins.get_foreign_keys(table)
        uniques = {u["name"] for u in ins.get_unique_constraints(table)}
        constraints = {c["name"] for c in ins.get_check_constraints(table)}
        checks[kind + "_required_scope"] = all(
            not columns[c]["nullable"]
            for c in (
                *SCOPE,
                "input_fingerprint",
                "pins_digest",
                "owner_actor_id",
                "request_json",
                "result_json",
                "provenance_json",
            )
        )
        checks[kind + "_canonical_refs"] = {
            "projects",
            "analysis_snapshots",
            "project_versions",
            "metadata_versions",
        } <= {fk["referred_table"] for fk in fks}
        checks[kind + "_scoped_parents"] = all(
            any(
                f["referred_table"] == TABLES[p]
                and f["constrained_columns"] == [*SCOPE, p.lower() + "_result_id"]
                for f in fks
            )
            for p in PARENTS[kind]
        )
        checks[kind + "_retry_scope_uniqueness"] = {
            "uq_j_" + kind.lower() + "_scope",
            "uq_j_" + kind.lower() + "_input",
        } <= uniques
        checks[kind + "_typed_version_subject"] = {
            "ck_j_" + kind.lower() + "_subject",
            "ck_j_" + kind.lower() + "_version",
        } <= constraints
        checks[kind + "_immutable_scoped_insertion"] = {
            (table, "tr_j_immutable"),
            (table, "tr_j_scope"),
        } <= triggers
    checks["referential_link_only"] = {
        "compliance_obligation_results",
        "regulation_applicability_results",
    } <= {f["referred_table"] for f in ins.get_foreign_keys("obligation_applicability_links")}
    checks["alias_is_not_result_store"] = "result_json" not in {
        c["name"] for c in ins.get_columns("decision_request_keys")
    }
    checks["immutable_scoped_aliases"] = {
        ("decision_request_keys", "tr_j_immutable"),
        ("decision_request_keys", "tr_j_request_scope"),
        ("obligation_applicability_links", "tr_j_app_scope"),
        ("obligation_applicability_links", "tr_j_immutable"),
    } <= triggers
    checks["existing_governance_immutable"] = {
        ("metadata_definitions", "tr_j_policy_guard"),
        ("metadata_versions", "tr_j_policy_guard"),
        ("analysis_snapshot_registry_pins", "tr_j_pin_guard"),
    } <= triggers
    checks["no_duplicate_authorities"] = not {
        "j_registry",
        "j_evidence",
        "j_legal_bases",
        "workflow_decision_results",
    } & set(ins.get_table_names())
    result = {
        "pass": all(checks.values()),
        "passed": sum(checks.values()),
        "total": len(checks),
        "checks": checks,
    }
    print(json.dumps(result, indent=2))
    if directory := os.getenv("EVIDENCE_DIR"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        (Path(directory) / "phase1j_schema_check.json").write_text(json.dumps(result, indent=2))
    engine.dispose()
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()

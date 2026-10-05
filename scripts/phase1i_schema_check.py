"""Measured PostgreSQL Phase1I schema proof preserving canonical source identities."""

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
    table = "regulation_applicability_results"
    columns = {c["name"]: c for c in ins.get_columns(table)}
    checks = {c["name"] for c in ins.get_check_constraints(table)}
    unique = {c["name"] for c in ins.get_unique_constraints(table)}
    indexes = {c["name"] for c in ins.get_indexes(table)}
    fks = {f["referred_table"] for f in ins.get_foreign_keys(table)}
    with engine.connect() as conn:
        revision = conn.scalar(text("SELECT version_num FROM alembic_version"))
        triggers = set(
            conn.scalars(
                text(
                    "SELECT DISTINCT trigger_name FROM information_schema.triggers "
                    "WHERE trigger_schema='public'"
                )
            )
        )
    results = {
        "phase1i_lineage": revision_at_or_after(revision, "0009_phase1i"),
        "canonical_result": table in ins.get_table_names(),
        "canonical_project": "projects" in fks,
        "canonical_snapshot": "analysis_snapshots" in fks,
        "canonical_jurisdiction": "jurisdictions" in fks,
        "canonical_regulation_version": "knowledge_document_versions" in fks,
        "canonical_profile_versions": "metadata_versions" in fks,
        "canonical_evidence_run": "retrieval_runs" in fks,
        "exact_subject_identity": {"subject_type", "subject_id"} <= columns.keys(),
        "trusted_owner_actor": "owner_actor_id" in columns,
        "formal_result_payload": "result_json" in columns,
        "reference_only_request": "request_json" in columns,
        "retry_fingerprint": "input_fingerprint" in columns,
        "snapshot_index": "ix_applicability_snapshot" in indexes,
        "tenant_index": "ix_regulation_applicability_results_tenant_id" in indexes,
        "retry_unique": "uq_applicability_resolution" in unique,
        "subject_constraint": "ck_applicability_subject" in checks,
        "six_status_constraint": "ck_applicability_status" in checks,
        "immutable_results": "phase1i_applicability_immutable" in triggers,
        "immutable_profiles": "phase1i_metadata_immutable" in triggers,
        "immutable_profile_identity": "phase1i_definition_immutable" in triggers,
        "immutable_snapshot_pins": "phase1i_pin_immutable" in triggers,
        "no_duplicate_regulation_store": not {
            "regulations",
            "regulation_versions",
            "country_profiles",
            "scenario_profiles",
            "legal_bases",
        }
        & set(ins.get_table_names()),
        "required_scope_columns_nonnullable": all(
            not columns[c]["nullable"]
            for c in (
                "tenant_id",
                "project_id",
                "analysis_snapshot_id",
                "jurisdiction_id",
                "subject_id",
                "regulation_version_ref",
            )
        ),
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
        (Path(directory) / "phase1i_schema_check.json").write_text(json.dumps(result, indent=2))
    engine.dispose()
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()

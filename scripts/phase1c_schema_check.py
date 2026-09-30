from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import inspect, text

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence import metadata_models as _metadata_models  # noqa: F401
from crossborder_compliance.infrastructure.persistence.db import build_engine
from crossborder_compliance.infrastructure.persistence.models import Base


REQUIRED_TABLES = {
    "metadata_definitions",
    "metadata_versions",
    "metadata_bindings",
    "classification_scheme_versions",
    "classification_bindings",
    "classification_applicability_metadata",
    "model_providers",
    "model_provider_versions",
    "model_definitions",
    "model_deployments",
    "model_capabilities",
    "model_routing_profiles",
    "model_health_metadata",
    "prompt_definitions",
    "prompt_versions",
    "prompt_bindings",
    "prompt_variable_schemas",
    "prompt_reviews",
    "prompt_publish_records",
    "rule_definitions",
    "rule_versions",
    "rule_bindings",
    "rule_test_cases",
    "rule_publish_records",
    "template_definitions",
    "template_versions",
    "template_bindings",
    "template_field_schemas",
    "template_reviews",
    "template_publish_records",
    "knowledge_collections",
    "knowledge_collection_versions",
    "knowledge_bindings",
    "knowledge_scope_metadata",
    "knowledge_source_definitions",
    "admin_change_sets",
    "admin_review_tasks",
    "admin_publish_records",
    "registry_sync_events",
    "analysis_snapshot_registry_pins",
}

FORBIDDEN_SECRET_COLUMNS = {
    "api_key",
    "access_token",
    "refresh_token",
    "password",
    "client_secret",
    "credential",
    "credential_value",
}


def _write(name: str, body: str) -> None:
    evidence_dir = Path(os.getenv("EVIDENCE_DIR", "artifacts/phase1a-runtime"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / name).write_text(body.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    metadata_tables = set(Base.metadata.tables)
    with engine.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    missing = sorted(REQUIRED_TABLES - tables)
    checkpoint_owned = sorted(name for name in metadata_tables if name.startswith("checkpoint"))

    model_provider_version_cols = {
        col["name"] for col in inspector.get_columns("model_provider_versions")
    }
    secret_value_cols = sorted(FORBIDDEN_SECRET_COLUMNS & model_provider_version_cols)
    secret_ref_present = "secret_ref" in model_provider_version_cols

    def fk_targets(table: str) -> set[str]:
        return {fk["referred_table"] for fk in inspector.get_foreign_keys(table)}

    def unique_sets(table: str) -> set[tuple[str, ...]]:
        return {
            tuple(sorted(uq["column_names"] or []))
            for uq in inspector.get_unique_constraints(table)
        }

    assertions = {
        "phase1c_schema_present_under_current_head": revision in {"0003_phase1c", "0004_phase1d"},
        "all_phase1c_tables_exist": not missing,
        "domain_metadata_excludes_langgraph_checkpoints": not checkpoint_owned,
        "metadata_version_fk_to_definition": "metadata_definitions" in fk_targets("metadata_versions"),
        "snapshot_pin_fk_to_analysis_snapshot": "analysis_snapshots" in fk_targets("analysis_snapshot_registry_pins"),
        "classification_version_fk_to_phase1b_scheme": "classification_schemes" in fk_targets("classification_scheme_versions"),
        "model_provider_version_fk_verified": "model_providers" in fk_targets("model_provider_versions"),
        "model_deployment_fk_graph_verified": {
            "model_definitions",
            "model_provider_versions",
        }.issubset(fk_targets("model_deployments")),
        "prompt_version_fk_verified": "prompt_definitions" in fk_targets("prompt_versions"),
        "rule_version_fk_verified": "rule_definitions" in fk_targets("rule_versions"),
        "template_version_fk_verified": "template_definitions" in fk_targets("template_versions"),
        "knowledge_version_fk_verified": "knowledge_collections" in fk_targets("knowledge_collection_versions"),
        "registry_outbox_idempotency_unique": tuple(
            sorted(("tenant_id", "object_kind", "object_id", "version_id", "event_version"))
        ) in unique_sets("registry_sync_events"),
        "snapshot_pin_immutable_unique": tuple(
            sorted(("tenant_id", "analysis_snapshot_id", "pin_type", "logical_key"))
        ) in unique_sets("analysis_snapshot_registry_pins"),
        "metadata_definition_kind_code_unique": tuple(
            sorted(("tenant_id", "kind", "code"))
        ) in unique_sets("metadata_definitions"),
        "metadata_canonical_binding_unique": tuple(
            sorted(("tenant_id", "kind", "canonical_object_id"))
        ) in unique_sets("metadata_definitions"),
        "model_secret_ref_only": secret_ref_present and not secret_value_cols,
        "classification_results_still_formal_source": "classification_results" in tables
        and "data_classifications" not in tables,
        "workflow_stage_view_still_not_persisted": "workflow_stage_views" not in tables,
        "api_workflow_idempotency_still_separate": {
            "api_idempotency_records",
            "execution_idempotency_records",
        }.issubset(tables),
    }
    result = {
        "pass": all(assertions.values()),
        "alembic_revision": revision,
        "assertions": assertions,
        "missing_tables": missing,
        "checkpoint_owned_by_domain": checkpoint_owned,
        "forbidden_secret_columns": secret_value_cols,
        "table_count": len(tables),
    }
    print(json.dumps(result, indent=2, sort_keys=True))

    rows = ["| Assertion | Result |", "|---|---|"]
    rows.extend(
        f"| `{name}` | **{'PASS' if ok else 'FAIL'}** |"
        for name, ok in assertions.items()
    )
    _write(
        "phase1c_database_schema_result.md",
        "# Phase 1C Metadata / Registry Database Schema Result\n\n"
        f"**Decision: {'PASS' if result['pass'] else 'FAIL'}**\n\n"
        + "\n".join(rows)
        + f"\n\n- Alembic revision: `{revision}`"
        + f"\n- Table count: `{len(tables)}`"
        + f"\n- Missing Phase 1C tables: `{missing}`",
    )
    _write(
        "phase1c_security_result.md",
        "# Phase 1C Security Boundary Result\n\n"
        f"- model secret_ref column present: **{'PASS' if secret_ref_present else 'FAIL'}**\n"
        f"- forbidden secret-value columns absent: **{'PASS' if not secret_value_cols else 'FAIL'}**\n"
        f"- forbidden columns found: `{secret_value_cols}`",
    )
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()

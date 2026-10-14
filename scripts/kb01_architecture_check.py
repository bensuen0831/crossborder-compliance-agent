"""Additive KB01 management constraints; no historical architecture rule is removed."""

import subprocess
from pathlib import Path

from scripts.kb01_ownership import BASE, overlay


def check(root):
    root = Path(root)

    def read(path):
        return (root / path).read_text()

    prefix = "src/crossborder_compliance/infrastructure/persistence/"
    taxonomy = read(prefix + "knowledge_taxonomy.py")
    document = read(prefix + "knowledge_document_management.py")
    models = read(prefix + "knowledge_management_models.py")
    metadata = read(prefix + "metadata_repositories.py")
    policy = read("src/crossborder_compliance/domain/knowledge_management.py")
    migration = read("alembic/versions/0021_kb01_taxonomy_operations.py")
    permissions = read("src/crossborder_compliance/application/knowledge_taxonomy.py")
    old_legal = "src/crossborder_compliance/domain/decision_engine.py"
    old_invocation = "src/crossborder_compliance/application/intake_services.py"

    def unchanged(path):
        return (root / path).read_bytes() == subprocess.check_output(
            ["git", "show", BASE + ":" + path], cwd=root
        )

    grant_check = 'f"knowledge:{operation}" not in context.permission.scopes' in policy
    policy_check = "KNOWLEDGE_MANAGEMENT_POLICY_NOT_CONFIGURED_OR_AMBIGUOUS" in taxonomy
    enabled_check = 'payload.get("management_schema") == "KB01_TAXONOMY_V1"' in metadata
    return {
        "kb01_reuses_canonical_metadata_lifecycle": "self.lifecycle._transition_in_session("
        in taxonomy,
        "kb01_reuses_canonical_knowledge_lifecycle": "self.owner._governance_in_session("
        in document,
        "kb01_reuses_canonical_document_identity": "self.owner._create_document_in_session("
        in document,
        "kb01_reuses_canonical_document_version": "self.owner._create_version_in_session("
        in document,
        "kb01_exact_classification_is_relational": all(
            x in models
            for x in (
                "fk_knowledge_label_version_scope",
                "fk_knowledge_label_metadata_scope",
                "metadata_version_id",
            )
        ),
        "kb01_published_classification_cannot_mutate": "KB01_PUBLISHED_LABEL_IMMUTABLE"
        in migration,
        "kb01_candidate_confirmation_unchanged": unchanged(old_invocation),
        "kb01_formal_legal_algorithms_unchanged": unchanged(old_legal),
        "kb01_metadata_merge_has_no_historical_rebinding": '"historical_rebinding": False'
        in taxonomy,
        "kb01_published_taxonomy_requires_independent_review": "INDEPENDENT_HUMAN_REVIEW_REQUIRED"
        in taxonomy,
        "kb01_current_operation_grants_are_required": grant_check,
        "kb01_delete_and_archive_grants_are_distinct": all(
            x in permissions for x in ('"taxonomy:delete"', '"taxonomy:archive"')
        ),
        "kb01_missing_retention_policy_fails_closed": policy_check,
        "kb01_draft_delete_checks_references_and_age": all(
            x in document
            for x in (
                'impact["eligible_draft"]',
                "policy.draft_retention_seconds",
                "KNOWLEDGE_DOCUMENT_DELETE_PROTECTED",
            )
        ),
        "kb01_operation_audit_is_append_only": "KB01_ADMIN_AUDIT_IMMUTABLE" in migration,
        "kb01_hold_history_is_retained": "KB01_HOLD_HISTORY_IMMUTABLE" in migration,
        "kb01_unsafe_schema_downgrade_refuses": "KB01_TAXONOMY_DOWNGRADE_REFUSED" in migration,
        "kb01_registry_discovery_respects_versioned_enablement": enabled_check
        and 'not payload.get("enabled", True)' in metadata,
        "kb01_finite_committed_source_scope": overlay(root)[0],
        "kb01_stage2_formal_boundary_unchanged": unchanged(
            "src/crossborder_compliance/infrastructure/persistence/formal_result_repository.py"
        ),
    }

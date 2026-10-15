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
    storage = read("src/crossborder_compliance/infrastructure/knowledge_binary_storage.py")
    sandbox = read("src/crossborder_compliance/infrastructure/knowledge_process_sandbox.py")
    archive = read("src/crossborder_compliance/infrastructure/knowledge_archive_process.py")
    batches = read(prefix + "knowledge_batches.py")
    uploads = read(prefix + "knowledge_uploads.py")
    worker = read("src/crossborder_compliance/infrastructure/knowledge_import_worker.py")
    binary_migration = read("alembic/versions/0022_kb01_binary_transport.py")

    def unchanged(path):
        return (root / path).read_bytes() == subprocess.check_output(
            ["git", "show", BASE + ":" + path], cwd=root
        )

    grant_check = 'f"knowledge:{operation}" not in context.permission.scopes' in policy
    policy_check = "KNOWLEDGE_MANAGEMENT_POLICY_NOT_CONFIGURED_OR_AMBIGUOUS" in taxonomy
    enabled_check = 'payload.get("management_schema") == "KB01_TAXONOMY_V1"' in metadata
    canonical_batch_create = "self.documents.create_in_session(s, document)" in batches
    binary_downgrade_refuses = "KB01_BINARY_TRANSPORT_DOWNGRADE_REFUSED" in binary_migration
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
        "kb01_binary_storage_requires_versioned_provider": "S3_OBJECT_VERSIONING_REQUIRED"
        in storage
        and "VersionId=version" in storage,
        "kb01_binary_transport_is_streamed": "body.read(8 * 1024**2)" in storage
        and "part_chunks(source, size)" in worker
        and ".read_bytes(" not in storage + worker,
        "kb01_binary_worker_is_not_workflow_runtime": "WorkflowRuntime" not in worker
        and "AnalysisSnapshot" not in worker,
        "kb01_scanner_is_actual_isolated_process": '"/usr/bin/clamscan"' in sandbox
        and '"--network=none"' in sandbox
        and '"--read-only"' in sandbox,
        "kb01_isolated_process_has_resource_bounds": all(
            value in sandbox
            for value in (
                '"--cap-drop=ALL"',
                '"--pids-limit=64"',
                "KNOWLEDGE_PROCESS_SCRATCH_LIMIT",
                "KNOWLEDGE_PROCESS_DISK_BUDGET_EXHAUSTED",
                "KNOWLEDGE_PROCESS_OUTPUT_LIMIT",
            )
        ),
        "kb01_archive_supports_real_rar4_rar5_zip": all(
            value in archive
            for value in (
                "archive_read_support_format_zip",
                "archive_read_support_format_rar",
                "archive_read_support_format_rar5",
                "archive_read_data",
            )
        ),
        "kb01_archive_path_policy_is_shared": "domain.knowledge_paths import safe_relative_path"
        in archive
        and "ARCHIVE_LINK_OR_SPECIAL_FILE_REFUSED" in archive,
        "kb01_batch_mapping_uses_canonical_document_owner": canonical_batch_create
        and "self.uploads.attach_in_session(" in batches,
        "kb01_batch_worker_cannot_publish_knowledge": all(
            value not in worker
            for value in (
                "_governance_in_session",
                "create_document",
                "create_version",
                "PUBLISHED",
            )
        ),
        "kb01_unverified_batch_member_cannot_map": "KNOWLEDGE_BATCH_UPLOAD_NOT_VERIFIED" in batches
        and "KNOWLEDGE_BINARY_NOT_ATTACHABLE" in uploads,
        "kb01_import_original_and_manifest_are_immutable": all(
            value in binary_migration
            for value in (
                "KB01_ORIGINAL_BINARY_IDENTITY_IMMUTABLE",
                "KB01_IMPORT_ITEM_IDENTITY_IMMUTABLE",
                "KB01_IMPORT_MANIFEST_IMMUTABLE",
            )
        ),
        "kb01_binary_downgrade_preserves_operational_receipts": binary_downgrade_refuses
        and "admin_operation_receipts WHERE operation" in binary_migration,
    }

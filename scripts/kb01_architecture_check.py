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
    ingestion = read("src/crossborder_compliance/application/knowledge_services.py")
    extraction = read("src/crossborder_compliance/infrastructure/knowledge_binary_extraction.py")
    native = read("src/crossborder_compliance/infrastructure/native_document_extraction.py")
    native_host = read("src/crossborder_compliance/infrastructure/knowledge_native_parser.py")
    native_worker = read("src/crossborder_compliance/infrastructure/knowledge_management_worker.py")
    native_repo = read(prefix + "knowledge_repositories.py")
    alignment = read(prefix + "knowledge_translation_alignment.py")
    alignment_contract = read(
        "src/crossborder_compliance/domain/knowledge_translation_alignment.py"
    )
    readiness = read(prefix + "regulatory_acceptance.py")
    gold_governance = read(prefix + "regulatory_acceptance_governance.py")
    gold_contract = read("src/crossborder_compliance/domain/regulatory_acceptance.py")
    source_migration = read("alembic/versions/0023_kb01_evidence_source_reference.py")

    statistics = read(prefix + "knowledge_statistics.py")
    management_ui = read("frontend/src/features/knowledge-management/KnowledgeManagement.tsx")
    browser_upload = read("frontend/src/features/knowledge-management/uploads.ts")
    hash_worker = read("frontend/src/features/knowledge-management/hash.worker.ts")
    hash_stream = read("frontend/src/features/knowledge-management/streamDigest.ts")
    capabilities = read("src/crossborder_compliance/interfaces/api/routes/knowledge_management.py")

    def unchanged(path):
        return (root / path).read_bytes() == subprocess.check_output(
            ["git", "show", BASE + ":" + path], cwd=root
        )

    grant_check = 'f"knowledge:{operation}" not in context.permission.scopes' in policy
    policy_check = "KNOWLEDGE_MANAGEMENT_POLICY_NOT_CONFIGURED_OR_AMBIGUOUS" in taxonomy
    enabled_check = 'payload.get("management_schema") == "KB01_TAXONOMY_V1"' in metadata
    canonical_batch_create = "self.documents.create_in_session(s, document)" in batches
    binary_downgrade_refuses = "KB01_BINARY_TRANSPORT_DOWNGRADE_REFUSED" in binary_migration
    source_downgrade_refuses = "KB01_EVIDENCE_REFERENCE_DOWNGRADE_REFUSED" in source_migration
    shared_native_alias = (
        "IsolatedNativeKnowledgeParser = IsolatedNativeDocumentParser" in native_host
    )
    manifests = read(prefix + "knowledge_manifest_imports.py")
    manifest_ddl = read("alembic/versions/0024_kb01_import_manifest_records.py")
    manifest_models = read(prefix + "knowledge_manifest_models.py")
    binary_upload = read("src/crossborder_compliance/domain/knowledge_upload.py")
    return {
        "kb01_archive_members_require_actual_verified_upload_before_mapping": (
            'upload.status != "VERIFIED"' in batches and '"mapping_available"' in batches
        ),
        "kb01_browser_uses_backend_owned_scan_pending_projection": "pendingBatchTransport"
        in management_ui
        and "item.transport_pending" in management_ui
        and "item.mapping_available" in management_ui,
        "kb01_manifest_is_scoped_to_existing_import_batch": "knowledge_import_batches"
        in manifest_models,
        "kb01_manifest_and_rows_are_append_only": "BEFORE UPDATE OR DELETE" in manifest_ddl,
        "kb01_manifest_actor_is_server_owned": "created_by=self.context.permission.actor_id"
        in manifests,
        "kb01_manifest_verifies_original_digest": "MANIFEST_ORIGINAL_DIGEST_MISMATCH" in manifests,
        "kb01_manifest_limits_are_governed": "policy.manifest" in manifests,
        "kb01_manifest_does_not_create_knowledge": "KnowledgeVersionEntity(" not in manifests,
        "kb01_confirmed_catalogue_row_has_relational_identity": "manifest_record_id" in batches
        and "ForeignKeyConstraint" in manifest_ddl,
        "kb01_catalogues_are_not_legal_original_formats": "MANIFEST_FORMATS" in binary_upload
        and "DOCUMENT_FORMATS" in binary_upload,
        "kb01_scope_management_reuses_knowledge_binding_owner": "self.owner.add_binding"
        in document,
        "kb01_scope_actor_is_server_owned": '"submitted_by": self.context.permission.actor_id'
        in document,
        "kb01_quality_and_readiness_are_canonical_projections": "runtime_readiness(" in document
        and "KnowledgeQualityResultEntity" in document,
        "kb01_binding_contributor_cannot_self_approve": '"DOCUMENT_BIND"' in native_repo
        and "submitted_by" in native_repo,
        "kb01_tree_projects_published_canonical_parents": all(
            x in taxonomy
            for x in (
                "child.parent_definition_id",
                'v.lifecycle_status == "ACTIVE"',
                "version.version_id == definition.active_version_id",
            )
        ),
        "kb01_tree_does_not_publish_draft_parent_proposals": "query.order_by(definition.code"
        in taxonomy
        and "def tree(" in permissions,
        "kb01_upload_limits_come_from_governed_policy_api": "def policy_view(" in uploads
        and '"/upload-policy"' in browser_upload,
        "kb01_body_abort_is_not_converted_to_success": "AbortError"
        in read("frontend/src/api/client.ts"),
        "kb01_alignment_reuses_canonical_translation_store": "k.KnowledgeTranslationEntity("
        in alignment
        and "__tablename__" not in alignment,
        "kb01_alignment_pins_exact_clause_citation_and_text": all(
            x in alignment
            for x in (
                "source_content_hash",
                "target_content_hash",
                "source_citation_id",
                "target_citation_id",
                "source_text_sha256",
                "target_text_sha256",
            )
        ),
        "kb01_alignment_is_independently_reviewed_with_cas": all(
            x in alignment
            for x in (
                "INDEPENDENT_TRANSLATION_REVIEW_REQUIRED",
                "TRANSLATION_REVIEW_VERSION_CONFLICT",
                "self.context.permission.actor_id",
            )
        ),
        "kb01_alignment_cannot_claim_official_legal_authority": '"official_evidence": False'
        in alignment
        and 'Literal["HUMAN"]' in alignment_contract,
        "kb01_alignment_generic_legacy_review_cannot_bypass_owner": (
            "USE_TYPED_TRANSLATION_ALIGNMENT_REVIEW" in native_repo
        ),
        "kb01_f0_records_reuse_metadata_lifecycle": "MetadataLifecycleService" in readiness
        and "PostgresAdminMetadataRepository" in readiness,
        "kb01_f0_has_no_schema_or_formal_result_owner": "__tablename__"
        not in readiness + gold_contract
        and "FormalResultEntity(" not in readiness,
        "kb01_f0_synthetic_data_cannot_be_real_acceptance": "SYNTHETIC_GOVERNED_TEST_DATA"
        in gold_contract
        and "ENGINEERING_READINESS_ONLY" in readiness,
        "kb01_f0_l2_requires_verified_original_source": "VERIFIED" in gold_governance
        and "KnowledgeBinaryAttachmentEntity" in gold_governance,
        "kb01_f0_approval_is_independent_and_actor_bound": "actor_id" in gold_governance
        and "REGULATORY_EXPERT_AUTHORIZATION" in gold_contract,
        "kb01_f0_readiness_does_not_claim_f1_execution": "NOT_EXECUTED" in readiness
        and "READY_FOR_INDEPENDENT_ACCEPTANCE" in readiness,
        "kb01_statistics_shares_authorized_document_scope": "self.documents.scoped_query("
        in statistics,
        "kb01_statistics_uses_sql_distinct_document_counts": (
            "func.count(func.distinct(v.document_id))" in statistics
        ),
        "kb01_statistics_requires_both_current_grants": all(
            x in statistics for x in ('"statistics:read"', '"document:read"')
        ),
        "kb01_admin_uses_existing_authenticated_shell": "KnowledgeManagement"
        in read("frontend/src/features/admin/AdminFeature.tsx")
        and "KnowledgeManagementClient(admin)" in management_ui,
        "kb01_admin_capabilities_are_server_owned": "context.permission.scopes" in capabilities
        and 'scope != "knowledge:admin"' in capabilities,
        "kb01_browser_hashes_in_worker_and_bounded_chunks": "new Worker(" in browser_upload
        and "digestStream(data.stream())" in hash_worker
        and "stream.getReader()" in hash_stream
        and "file.slice(" in browser_upload,
        "kb01_signed_transfer_omits_application_credentials": 'credentials: "omit"'
        in browser_upload
        and 'redirect: "error"' in browser_upload,
        "kb01_clause_preview_is_exact_version_and_paged": "version.knowledge_version_id" in document
        and "original_excerpt" in document
        and '"citation_id": n.citation_id' in document,
        "kb01_item_retry_preserves_canonical_version": "KNOWLEDGE_BATCH_ITEM_SOURCE_IMMUTABLE"
        in batches
        and "expected_item_record_version" in batches,
        "kb01_failure_export_requires_own_grant": '"batch:export"' in batches
        and "technical_retry_available" in batches,
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
        "kb01_native_source_uses_existing_ingestion_owner": "self.repository.complete_ingestion("
        in ingestion
        and "binary_extractor.extract(binary_source)" in ingestion,
        "kb01_native_original_is_not_replaced_by_parse_json": 'binary_source["artifact_ref"]'
        in ingestion
        and "if binary_source is None:" in ingestion,
        "kb01_native_source_has_no_fake_project_snapshot": all(
            value not in extraction + native + native_host
            for value in (
                "ProjectEntity",
                "AnalysisSnapshotEntity",
                "create_snapshot",
                "WorkflowRun",
            )
        ),
        "kb01_native_config_and_original_pins_are_revalidated": "KNOWLEDGE_BINARY_PIN_MISMATCH"
        in native_repo
        and "expected_parser.model_dump" in native_repo,
        "kb01_native_extract_is_offline_and_bounded": "max_native_output_bytes" in native_host
        and "KNOWLEDGE_PROCESS_DISK_BUDGET_EXHAUSTED" in native_host,
        "kb01_source_xml_refuses_external_entities": "NATIVE_XML_DECLARATION_REFUSED" in native,
        "kb01_native_ocr_has_page_confidence_and_quality_gate": "ocr_minimum_measured_confidence"
        in native
        and 'checks["native_extraction_quality"]' in native_repo,
        "kb01_import_service_uses_scoped_identity": "KNOWLEDGE_WORKER_REQUIRES_SCOPED_IDENTITY"
        in native_worker
        and "RepositoryContext.system" not in native_worker,
        "kb01_source_reference_widening_does_not_rewrite_rows": source_downgrade_refuses
        and "UPDATE evidence_references" not in source_migration,
        "kb01_parser_ports_share_identity_free_native_core": shared_native_alias
        and "StreamNativeDocumentParserPort"
        in read("src/crossborder_compliance/application/document_ports.py"),
    }

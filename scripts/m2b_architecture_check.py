"""Additive M2-B temporal checks; frozen architecture rules stay unchanged."""
import json
from pathlib import Path


def check(root):
    root = Path(root)
    def source(relative):
        return "".join((root / relative).read_text().split())
    prefix = "src/crossborder_compliance/infrastructure/persistence/"
    models = source(prefix + "context_models.py")
    writes = source(prefix + "context_repositories.py")
    exact = source(prefix + "context_temporal.py")
    phase_f = source(prefix + "knowledge_repositories.py")
    phase_h = source(prefix + "classification_repository.py")
    phase_i = source(prefix + "country_compliance_repository.py")
    inputs = source(prefix + "document_snapshot_inputs.py")
    upload = source(prefix + "project_document_inputs.py")
    frontend = source("frontend/src/features/intake/documentApi.ts")
    storage = source("src/crossborder_compliance/infrastructure/document_storage.py")
    document_service = source("src/crossborder_compliance/application/document_services.py")
    models_d = source(prefix + "document_models.py")
    canonical = source("src/crossborder_compliance/workflows/canonical.py")
    migration = source("alembic/versions/0013_m2b_context_temporal_contract.py")
    checks = {
        "stable_canonical_data_item_identity": "DataItemEntity.name==canonical_name" in writes
        and "returnUUID(item.data_item_id)" in writes,
        "immutable_inventory_version_detail": '"tenant_id","data_item_id","version"' in models
        and "IMMUTABLE_INVENTORY_VERSION_REWRITE" in writes and "immutableformalcontextversion" in migration,
        "inventory_version_scoped_membership": "DataItemResolutionDetailEntity.version==version" in exact,
        "inventory_version_scoped_candidate_links": "DataItemCandidateLinkEntity.data_inventory_version==version" in writes,
        "inventory_version_scoped_source_trace_links": "DataItemSourceTraceLinkEntity.data_inventory_version==version" in exact,
        "snapshot_cannot_see_future_provenance": "AnalysisSnapshotParseRunPinEntity.analysis_snapshot_id==str(snapshot_id)" in exact
        and "AnalysisSnapshotParseRunPinEntity.parse_run_id==d.SourceTraceDetailEntity.parse_run_id" in exact,
        "phase1f_reads_exact_inventory_version": "exact_item_detail(s,self.tenant_id,item_id,run.data_inventory_version)" in phase_f,
        "phase1h_reads_exact_inventory_version": "exact_item_detail(s,self.tenant,data_item_id,pin.data_inventory_version)" in phase_h,
        "phase1i_reads_exact_inventory_version": "exact_item_detail(s,self.tenant,request.subject_id,pin.data_inventory_version)" in phase_i,
        "snapshot_evidence_scoped_to_input_universe": "item_trace_ids(session,self.tenant,item_id,inventory_version,snapshot_id)" in phase_h,
        "no_latest_version_fallback": all(term not in exact for term in (".desc()", "max(", "<=version"))
        and "PHASE1E_SNAPSHOT_CONTEXT_PIN_REQUIRED" in phase_f,
        "historical_snapshot_immutable": "repo.pin_parse_run(" in inputs and "document_input_universe_pinned" in inputs,
        "unknown_legacy_provenance_not_fabricated": "data_inventory_versionISNULL" in migration
        and "candidate_resolutionsr" in migration and "r.actionIN('ACCEPTED','MERGED')" in migration,
        "version_scoped_product_and_flow_links": "item_products(s,self.tenant_id,item_id,run.data_inventory_version,snapshot_id)" in phase_f
        and "flow_item_ids(s,self.tenant,request.subject_id,pin.data_inventory_version)" in phase_i,
    }
    checks.update({
        "binary_not_in_workflow_state": all(x not in canonical for x in ("content:bytes", "binary:bytes", "base64")),
        "document_source_of_truth_is_single": "PostgresDocumentIntelligenceRepository" in upload and all(x not in upload for x in ("M2Document", "UploadedFileRecord")),
        "parse_run_source_of_truth_is_single": "repo.create_parse_task(" in upload and "service.process_task(task_id)" in upload,
        "document_candidate_requires_genuine_source_trace": "SourceTraceDetailEntity.parse_run_id" in exact,
        "no_fake_parse_run": all(x not in upload for x in ("DocumentParseRunEntity(", "SourceTraceRefEntity(")),
        "manual_and_document_provenance_distinct": "USER_INPUT" in source(prefix + "structured_intake.py") and "upload_provenance_json" in models_d,
        "snapshot_pins_exact_document_universe": "ProjectVersionDocumentLinkEntity.project_version_id==version.project_version_id" in inputs and "parse_run_ids=parse_run_ids" in source("src/crossborder_compliance/infrastructure/intake_composition.py"),
        "confirmed_snapshot_is_not_mutated": "analysis snapshot document universe is immutable".replace(" ", "") in source(prefix + "document_repositories.py"),
        "binary_storage_is_infrastructure_boundary": "ObjectStoragePort" in document_service and "classFileObjectStorageAdapter" in storage,
        "frontend_does_not_authorize_upload": all(x not in frontend for x in ("tenant_id", "storage_ref", "policy_id", "PermissionContext")),
        "frontend_does_not_formalize_facts": all(x not in frontend for x in ("BusinessFact", "risk_score", "classification_result", "final_path")),
        "document_parser_not_reimplemented": "default_native_parsers()" in upload,
        "cross_source_conflict_uses_existing_authority": "BUSINESS_FACT_CONFLICT" in source("src/crossborder_compliance/application/context_services.py") and "ContextConflictEntity" in writes,
    })
    return {"pass": all(checks.values()), "passed": sum(checks.values()), "total": len(checks), "checks": checks}


if __name__ == "__main__":
    result = check(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(not result["pass"])

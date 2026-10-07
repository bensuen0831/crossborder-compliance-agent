"""Additive M2-A checks; the existing 151 architecture assertions remain intact."""

import json
from pathlib import Path


def check(root):
    root = Path(root)

    def source(path):
        return "".join((root / path).read_text().split())

    application = source("src/crossborder_compliance/application/intake_services.py")
    persistence = source("src/crossborder_compliance/infrastructure/persistence/project_intake.py")
    composition = source("src/crossborder_compliance/infrastructure/intake_composition.py")
    structured = source(
        "src/crossborder_compliance/infrastructure/persistence/structured_intake.py"
    )
    workflow = source("src/crossborder_compliance/interfaces/api/routes/workflow.py")
    routing = source("src/crossborder_compliance/application/workflow_formal.py")
    ui = source("frontend/src/features/intake/persistence.ts")
    checks = {
        "intake_draft_not_formal_input": 'ifrow.status!="DRAFT":' in persistence
        and "CONFIRMED_INTAKE_IMMUTABLE" in persistence,
        "confirmed_intake_required_for_snapshot": 'row.status="CONFIRMED"' in persistence
        and 'version.status!="CONFIRMED"' in structured,
        "snapshot_pins_intake_version": "project_version_id=row.project_version_id" in persistence
        and "source_version=str(version.version_no)" in structured,
        "no_parallel_project_source_of_truth": "PostgresProjectRepository(sessions,context)"
        in composition
        and "ProjectEntity(" in persistence,
        "no_parallel_intake_source_of_truth": "ProjectVersionEntity(" in persistence
        and "ProjectIntakeContext.model_validate(row.intake_json)" in persistence
        and 'create_model("IntakeFacts"' in application,
        "frontend_does_not_authorize": "PermissionContext" not in ui
        and "tenant_id:" not in ui
        and "policy_id:" not in ui,
        "frontend_does_not_create_formal_decision": all(
            x not in ui
            for x in (
                "risk_score:",
                "final_path:",
                "applicability_status:",
                "classification_result:",
            )
        ),
        "intake_metadata_is_registry_driven": "m.MetadataDefinitionEntity" in structured
        and "m.AnalysisSnapshotRegistryPinEntity(" in structured
        and "StructuredIntakeBinding.model_validate(raw)" in structured,
        "cross_tenant_intake_forbidden": "ProjectEntity.tenant_id==self.tenant_id" in persistence
        and "actor==self._context.permission.actor_id" in persistence,
        "workflow_start_requires_authorized_snapshot": (
            "scope(sf,context,project_id,snapshot_id,operation)"
        )
        in workflow
        and "authorized_intake_context(request,context,project_id)" in workflow
        and "authorize_pins(sessions,context,snapshot_id)" in composition,
        "browser_cannot_inject_policy_or_decision": 'model_config=ConfigDict(extra="forbid")'
        in application
        and '"provenance"' in application
        and '"project_id"' in application,
        "manual_fact_uses_canonical_provenance_without_fake_document": "ProvenanceDTO("
        in structured
        and 'source_type="USER_INPUT"' in structured
        and all(
            x not in structured
            for x in (
                "DocumentParseRunEntity(",
                "SourceTraceRefEntity(",
                "BusinessFactCandidateEntity(",
            )
        ),
        "missing_formal_facts_controlled_stop": "StageOutcomeCode.INSUFFICIENT_INPUT" in routing
        and "FORMAL_BUSINESS_FACT_REQUIRED" in routing,
    }
    return {
        "pass": all(checks.values()),
        "passed": sum(checks.values()),
        "total": len(checks),
        "checks": checks,
    }


if __name__ == "__main__":
    import sys

    result = check(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    sys.exit(not result["pass"])

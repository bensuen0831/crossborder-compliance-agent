"""Additive R1.1 owner checks; historical architecture checks remain intact."""

import ast
from pathlib import Path


def body(source, name):
    node = next(
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    )
    return ast.get_source_segment(source, node)


def calls(source):
    return {
        n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Call) and isinstance(n.func, (ast.Attribute, ast.Name))
    }


def check(root):
    root = Path(root)
    src = root / "src/crossborder_compliance"

    def read(path):
        return (src / path).read_text()

    owner = read("infrastructure/persistence/candidate_governance.py")
    prepare, decide = body(owner, "prepare"), body(owner, "resolve")
    validate = body(owner, "validate_preparation")
    authorize = body(owner, "confirmation_authorization")
    transfer = body(owner, "transfer_preparation_pins")
    confirm = body(read("infrastructure/persistence/project_intake.py"), "confirm_intake")
    compose = body(read("infrastructure/intake_composition.py"), "prepare_snapshot")
    context = read("infrastructure/persistence/context_repositories.py")
    candidates = body(context, "_authorized_candidates")
    mapping = body(context, "save_candidate_resolution")
    model = read("infrastructure/persistence/candidate_governance_models.py")
    scope = read("domain/llm_gateway.py")
    invocation = body(read("application/llm_invocation_services.py"), "invoke")
    normalize = read("application/context_services.py")
    migration = (root / "alembic/versions/0019_stage1_candidate_governance.py").read_text()
    audit = read("infrastructure/persistence/llm_gateway_audit.py")
    checks = {
        "candidate_preparation_is_pre_snapshot": "CandidatePreparationEntity(" in prepare
        and not ({"AnalysisSnapshotEntity", "WorkflowRunEntity"} & calls(prepare)),
        "candidate_preparation_is_bound_to_draft_version": 'version.status != "DRAFT"'
        in body(owner, "_draft")
        and "project_version_id=version.project_version_id" in prepare,
        "candidate_preparation_has_exact_document_pins": all(
            x in model
            for x in (
                "CandidatePreparationDocumentPinEntity",
                "document_versions.document_version_id",
                "document_parse_runs.document_parse_run_id",
            )
        )
        and "document_parse_runs" in migration,
        "candidate_preparation_has_exact_llm_pins": "CandidatePreparationRegistryPinEntity" in model
        and "freeze_llm_configuration" in calls(prepare)
        and "candidate_preparation_id=identity" in prepare,
        "llm_candidate_has_preparation_identity": all(
            x in model
            for x in (
                "CandidatePreparationCandidateEntity",
                "candidate_digest",
                "llm_request_id",
                "llm_invocation_group_id",
            )
        )
        and "LLM_COMPLETED" in migration,
        "llm_candidate_cannot_auto_formalize": "_require_candidate_authorization" in normalize
        and "CANDIDATE_CONFIRMATION_REQUIRED" in candidates,
        "policy_cannot_impersonate_user": "USER_CONFIRMATION" in mapping
        and "USER_CONFIRMED_DOCUMENT_CANDIDATE" in normalize,
        "confidence_cannot_authorize_candidate": "confidence"
        not in body(normalize, "_require_candidate_authorization")
        and "LLM_STRUCTURED_OUTPUT" in body(normalize, "_require_candidate_authorization"),
        "decision_set_is_append_only": "row.sealed = True" in decide
        and "stage1_candidate_append_only" in migration
        and "candidate_decision_sets" in migration,
        "decision_actor_is_server_owned": "submitted_by=self.context.permission.actor_id" in decide
        and "actor_id:" not in read("application/candidate_governance_services.py"),
        "decision_set_matches_candidate_universe": "decision_set.candidate_universe_digest != preparation.candidate_universe_digest"
        in authorize
        and "CandidateDecisionSetEntity" in model,
        "rejected_candidate_cannot_formalize": 'decision.action == "REJECT"' in candidates
        and "continue" in candidates,
        "edited_candidate_preserves_original_candidate": "**row" in candidates
        and "edited_payload_json" in candidates
        and "PREPARED_CANDIDATE_IMMUTABLE" in migration,
        "confirm_does_not_generate_candidates": "confirmation_authorization" in calls(confirm)
        and not ({"prepare_document_candidates", "prepare", "save_candidate"} & calls(compose)),
        "confirm_does_not_call_document_llm": "prepare_document_candidates"
        not in calls(confirm) | calls(compose)
        and "invoke" not in calls(confirm) | calls(compose),
        "confirm_uses_exact_preparation": confirm.index("confirmation_authorization(")
        < confirm.index("AnalysisSnapshotEntity(")
        and "candidate_decision_set_id" in confirm,
        "snapshot_copies_exact_preparation_pins": "PostgresSnapshotRegistryPinRepository"
        in transfer
        and all(
            x in transfer
            for x in ("**pin", 'pin["object_id"]', 'pin["version_id"]', "list_pins(preparation_id)")
        ),
        "stale_preparation_cannot_confirm": all(
            x in validate
            for x in (
                "project_version_id",
                "input_universe_digest",
                "parse_run_id",
                "candidate_universe_digest",
            )
        )
        and "CANDIDATE_PREPARATION_STALE" in validate,
        "draft_scope_is_not_fake_snapshot": all(
            x in audit for x in ("candidate_preparation_id", "project_version_id", "None")
        )
        and "self.analysis_snapshot_id is not None" in scope,
        "draft_scope_only_allows_candidate_extraction": "DOCUMENT_CANDIDATE_EXTRACTION"
        in invocation
        and "DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED" in invocation
        and "DRAFT_INVOCATION_PURPOSE_DENIED" in invocation,
        "candidate_confirmation_is_not_m2d_review": not (
            {"ReviewTaskEntity", "ReviewDecisionEntity"} & calls(owner)
        ),
        "existing_candidate_resolution_remains_formal_mapping": "CandidateResolutionEntity"
        in mapping
        and "formal" in mapping
        and "CandidateDecisionSetEntity" not in mapping,
        "historical_snapshot_does_not_require_0019_governance": confirm.index(
            'row.status == "CONFIRMED"'
        )
        < confirm.index("confirmation_authorization("),
        "stage2_not_started": not (
            {"generate_document", "generate_contract", "ReviewRuntime", "CorrectionRuntime"}
            & (calls(owner) | calls(compose))
        ),
    }
    return checks

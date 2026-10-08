"""Technical review resolution matrix; formal decision engines remain owners."""


def resolution_actions(*, stage, reasons, requirement_confirmation=False, modern=True):
    if not modern:
        return (), "UNAVAILABLE", "HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED"
    blocking = {
        "FACT_CONFLICT",
        "BUSINESS_FACT_CONFLICT",
        "PRODUCT_CONTEXT_CONFLICT",
        "JURISDICTION_UNRESOLVED",
        "INSUFFICIENT_EVIDENCE",
        "EVIDENCE_INSUFFICIENT",
        "CAPABILITY_NOT_CONFIGURED",
        "INSUFFICIENT_INPUT",
        "UNDETERMINED",
    }
    if requirement_confirmation and stage == "requirement" and not blocking.intersection(reasons):
        return ("APPROVE", "REJECT", "REQUEST_CHANGES"), "SAME_SNAPSHOT", None
    if {"FACT_CONFLICT", "BUSINESS_FACT_CONFLICT", "PRODUCT_CONTEXT_CONFLICT"}.intersection(
        reasons
    ):
        return ("SUBMIT_CORRECTION", "REJECT", "REQUEST_CHANGES"), "SUCCESSOR_SNAPSHOT", None
    return ("REQUEST_CHANGES", "REJECT"), "SUCCESSOR_SNAPSHOT", None

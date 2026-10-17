"""Acceptance reconciliation utilities; these do not execute compliance decisions."""

import hashlib
import json

from crossborder_compliance.domain.regulatory_acceptance import ExpectedRegulatorySemantics


def reconcile_semantics(
    expected: ExpectedRegulatorySemantics, observed: ExpectedRegulatorySemantics
):
    """Compare every declared semantic field, including exact legal-source identity.

    Callers obtain observations through authorized canonical result readers. This
    comparison alone does not certify the origin, a real Gold Standard or legal
    accuracy; it cannot grant F1 acceptance or write a formal result.
    """
    expected_data = expected.model_dump(mode="json")
    actual_data = observed.model_dump(mode="json")
    fields = {}
    for field, target in expected_data.items():
        actual = actual_data[field]
        if isinstance(target, list):

            def encode(value):
                return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

            wanted, received = (
                {encode(value) for value in target},
                {encode(value) for value in actual},
            )
            common = len(wanted & received)
            fields[field] = {
                "match": wanted == received,
                "expected_count": len(wanted),
                "observed_count": len(received),
                "precision": common / len(received) if received else 1.0 if not wanted else 0.0,
                "recall": common / len(wanted) if wanted else 1.0 if not received else 0.0,
                "missing_count": len(wanted - received),
                "unexpected_count": len(received - wanted),
            }
        else:
            fields[field] = {"match": target == actual}
    encoded = json.dumps(
        actual_data, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()
    return {
        "decision": "RECONCILIATION_MATCH"
        if all(value["match"] for value in fields.values())
        else "RECONCILIATION_MISMATCH",
        "fields": fields,
        "observed_semantics_sha256": hashlib.sha256(encoded).hexdigest(),
        "real_regulatory_legal_acceptance": "NOT_ESTABLISHED_BY_COMPARISON",
    }

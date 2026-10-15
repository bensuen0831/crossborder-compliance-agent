"""Export typed readiness schemas, never fabricated legal answers or expert approvals."""

import json
from pathlib import Path

from crossborder_compliance.domain.regulatory_acceptance import (
    ACCEPTANCE_TYPES,
    RegulatoryAcceptanceEvidence,
)


def export(root):
    target = root / "docs/stage1-gap-kb01/acceptance-templates"
    target.mkdir(parents=True, exist_ok=True)
    for kind, schema in {
        **ACCEPTANCE_TYPES,
        "REGULATORY_ACCEPTANCE_EVIDENCE": RegulatoryAcceptanceEvidence,
    }.items():
        (target / (kind.lower() + ".schema.json")).write_text(
            json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2) + "\n"
        )
    (target / "template_manifest.json").write_text(
        json.dumps(
            {
                "approval_status": "TEMPLATES_NOT_APPROVED_GOLD_STANDARDS",
                "f1": "BLOCKED_EXTERNAL_EVIDENCE_PENDING",
                "templates": sorted(
                    kind.lower() + ".schema.json"
                    for kind in [*ACCEPTANCE_TYPES, "REGULATORY_ACCEPTANCE_EVIDENCE"]
                ),
                "provided_real_gold_standards": 0,
                "provided_independent_real_expert_approvals": 0,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    export(Path(__file__).resolve().parents[2])

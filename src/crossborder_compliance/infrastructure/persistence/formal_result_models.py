"""Additive owning envelopes on the existing immutable formal decision infrastructure."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import mapped_column

from crossborder_compliance.infrastructure.persistence.decision_models import (
    SCOPE,
    DecisionResultColumns,
)
from crossborder_compliance.infrastructure.persistence.decision_models import TABLES as J_TABLES
from crossborder_compliance.infrastructure.persistence.models import Base

TABLES = {
    "CROSS_BORDER": "cross_border_assessment_results",
    "DOCUMENT_REQUIREMENT": "regulatory_document_requirement_results",
}
PARENTS = {
    "CROSS_BORDER": {"obligation_result_id": J_TABLES["OBLIGATION"]},
    "DOCUMENT_REQUIREMENT": {
        "obligation_result_id": J_TABLES["OBLIGATION"],
        "cross_border_result_id": TABLES["CROSS_BORDER"],
        "final_path_result_id": J_TABLES["FINAL_PATH"],
    },
}


def authority_model(kind):
    constraints = [
        UniqueConstraint(*SCOPE, "result_id", name="uq_c0_" + kind.lower() + "_scope"),
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "analysis_snapshot_id",
            "subject_type",
            "subject_id",
            "input_fingerprint",
            name="uq_c0_" + kind.lower() + "_input",
        ),
        CheckConstraint(
            "subject_type IN ('DATA_ITEM','DATA_FLOW','SCENARIO')",
            name="ck_c0_" + kind.lower() + "_subject",
        ),
        CheckConstraint(
            "contract_version='2.0' AND engine_version='FORMAL_RESULT_AUTHORITY_V2'",
            name="ck_c0_" + kind.lower() + "_version",
        ),
    ]
    attributes = {"__tablename__": TABLES[kind], "__module__": __name__}
    for col, table in PARENTS[kind].items():
        attributes[col] = mapped_column(String(36), nullable=True)
        constraints.append(
            ForeignKeyConstraint(
                (*SCOPE, col),
                tuple(table + "." + c for c in (*SCOPE, "result_id")),
                name="fk_c0_" + kind.lower() + "_" + col,
            )
        )
    attributes["__table_args__"] = tuple(constraints)
    return type(
        kind.title().replace("_", "") + "ResultEntity", (DecisionResultColumns, Base), attributes
    )


MODELS = {kind: authority_model(kind) for kind in TABLES}

"""The five authoritative J stage envelopes and referential/idempotency links only."""

from datetime import date

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from crossborder_compliance.infrastructure.persistence.models import Base, TenantAuditMixin

SCOPE = (
    "tenant_id",
    "project_id",
    "analysis_snapshot_id",
    "project_version_id",
    "context_version",
    "subject_type",
    "subject_id",
)
TABLES = {
    "OBLIGATION": "compliance_obligation_results",
    "CANDIDATE_PATH": "candidate_compliance_path_results",
    "RISK": "risk_assessment_results",
    "RECOMMENDATION": "compliance_recommendation_results",
    "FINAL_PATH": "final_compliance_path_results",
}
PARENTS = {
    "OBLIGATION": (),
    "CANDIDATE_PATH": ("OBLIGATION",),
    "RISK": ("CANDIDATE_PATH",),
    "RECOMMENDATION": ("CANDIDATE_PATH", "RISK"),
    "FINAL_PATH": ("OBLIGATION", "CANDIDATE_PATH", "RISK", "RECOMMENDATION"),
}


class DecisionResultColumns(TenantAuditMixin):
    result_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    analysis_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_snapshots.analysis_snapshot_id"), nullable=False
    )
    project_version_id: Mapped[str] = mapped_column(
        ForeignKey("project_versions.project_version_id"), nullable=False
    )
    context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    analysis_as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    jurisdiction_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    policy_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("metadata_versions.version_id"), nullable=True
    )
    upstream_refs: Mapped[list] = mapped_column(JSON, nullable=False)
    pins_json: Mapped[list] = mapped_column(JSON, nullable=False)
    provenance_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    pins_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(20), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(60), nullable=False)
    owner_actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    summary_status: Mapped[str] = mapped_column(String(60), nullable=False)
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)


def stage_model(kind):
    name = TABLES[kind]
    constraints = [
        UniqueConstraint(*SCOPE, "result_id", name="uq_j_" + kind.lower() + "_scope"),
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "analysis_snapshot_id",
            "subject_type",
            "subject_id",
            "input_fingerprint",
            name="uq_j_" + kind.lower() + "_input",
        ),
        CheckConstraint(
            "subject_type IN ('DATA_ITEM','DATA_FLOW','SCENARIO')",
            name="ck_j_" + kind.lower() + "_subject",
        ),
        CheckConstraint(
            "contract_version='2.0' AND engine_version='FORMAL_DECISION_V2'",
            name="ck_j_" + kind.lower() + "_version",
        ),
    ]
    attributes = {"__tablename__": name, "__module__": __name__}
    for parent in PARENTS[kind]:
        col = parent.lower() + "_result_id"
        attributes[col] = mapped_column(String(36), nullable=False)
        constraints.append(
            ForeignKeyConstraint(
                (*SCOPE, col),
                tuple(TABLES[parent] + "." + c for c in (*SCOPE, "result_id")),
                name="fk_j_" + kind.lower() + "_" + parent.lower(),
            )
        )
    attributes["__table_args__"] = tuple(constraints)
    return type(
        kind.title().replace("_", "") + "ResultEntity", (DecisionResultColumns, Base), attributes
    )


MODELS = {kind: stage_model(kind) for kind in TABLES}


class ObligationApplicabilityLinkEntity(TenantAuditMixin, Base):
    __tablename__ = "obligation_applicability_links"
    link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    obligation_result_id: Mapped[str] = mapped_column(
        ForeignKey("compliance_obligation_results.result_id"), nullable=False
    )
    applicability_result_id: Mapped[str] = mapped_column(
        ForeignKey("regulation_applicability_results.applicability_result_id"), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "obligation_result_id",
            "applicability_result_id",
            name="uq_j_applicability_link",
        ),
    )


class DecisionRequestKeyEntity(TenantAuditMixin, Base):
    """Request aliases reference immutable envelopes; they never store a second result."""

    __tablename__ = "decision_request_keys"
    request_key_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    stage_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_id: Mapped[str] = mapped_column(String(36), nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "project_id", "stage_kind", "idempotency_key", name="uq_j_request_key"
        ),
        CheckConstraint(
            "stage_kind IN ('OBLIGATION','CANDIDATE_PATH','RISK','RECOMMENDATION','FINAL_PATH')",
            name="ck_j_request_kind",
        ),
    )

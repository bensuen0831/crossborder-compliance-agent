"""Versioned scheme membership through the existing classification Admin repository."""

from datetime import date
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import select

from crossborder_compliance.domain.classification import ClassificationScheme
from crossborder_compliance.domain.rules import Contract
from crossborder_compliance.infrastructure.persistence import models as b


class CategoryDraft(Contract):
    category_id: UUID | None = None
    code: str = Field(min_length=1, max_length=100)


class LevelDraft(Contract):
    level_id: UUID | None = None
    code: str = Field(min_length=1, max_length=100)
    rank: int = Field(ge=0, strict=True)


class SchemeDraft(Contract):
    jurisdiction_ids: tuple[UUID, ...] = Field(min_length=1)
    categories: tuple[CategoryDraft, ...] = ()
    levels: tuple[LevelDraft, ...] = ()


def materialize_scheme(session, row):
    raw = row.applicability_json.get("phase1h")
    if raw is None:
        return
    draft = SchemeDraft.model_validate(raw)
    if not draft.categories and not draft.levels:
        raise ValueError("scheme needs at least one category or level")
    for jurisdiction in draft.jurisdiction_ids:
        if (
            session.scalar(
                select(b.JurisdictionEntity).where(
                    b.JurisdictionEntity.tenant_id == row.tenant_id,
                    b.JurisdictionEntity.jurisdiction_id == str(jurisdiction),
                )
            )
            is None
        ):
            raise LookupError("classification reference not found")
    members = {}
    for kind, drafts, model, pk in (
        ("categories", draft.categories, b.ClassificationCategoryEntity, "category_id"),
        ("levels", draft.levels, b.ClassificationLevelEntity, "level_id"),
    ):
        if len({d.code for d in drafts}) != len(drafts):
            raise ValueError("duplicate scheme member code")
        members[kind] = []
        for member in drafts:
            ident = member.category_id if kind == "categories" else member.level_id
            existing = session.scalar(
                select(model).where(
                    model.tenant_id == row.tenant_id,
                    model.scheme_id == row.scheme_id,
                    getattr(model, pk) == str(ident) if ident else model.code == member.code,
                )
            )
            if ident and existing is None:
                raise LookupError("classification member not found")
            if existing is not None and (
                existing.code != member.code or (kind == "levels" and existing.rank != member.rank)
            ):
                raise ValueError("immutable member differs; create a new member code")
            if existing is None:
                ident = uuid4()
                values = {
                    pk: str(ident),
                    "tenant_id": row.tenant_id,
                    "scheme_id": row.scheme_id,
                    "code": member.code,
                }
                values.update(
                    {"name": member.code} if kind == "categories" else {"rank": member.rank}
                )
                session.add(model(**values))
            else:
                ident = UUID(getattr(existing, pk))
            value = {pk: str(ident), "code": member.code}
            if kind == "levels":
                value["rank"] = member.rank
            members[kind].append(value)
    row.applicability_json = {
        **row.applicability_json,
        "phase1h": {"jurisdiction_ids": [str(v) for v in draft.jurisdiction_ids], **members},
    }


def scheme_dates(row, payload):
    for key in ("effective_from", "effective_to"):
        value = payload.get(key)
        if value is not None and type(value) is not date:
            if type(value) is not str:
                raise ValueError("scheme dates must be ISO dates")
            value = date.fromisoformat(value)
        setattr(row, key, value)
    if row.effective_from and row.effective_to and row.effective_to < row.effective_from:
        raise ValueError("invalid classification scheme date interval")


def validate_scheme(row):
    config = row.applicability_json.get("phase1h")
    if config is not None:
        return ClassificationScheme.model_validate(
            {
                **config,
                "tenant_id": row.tenant_id,
                "scheme_id": row.scheme_id,
                "scheme_version_id": row.scheme_version_id,
                "version": row.version_no,
                "lifecycle": row.lifecycle_status,
            }
        )
    return None

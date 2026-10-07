"""Governed generic test configuration, published before the snapshot is sealed."""

from uuid import uuid4

from sqlalchemy import select
from test_phase1i_postgres import publish_config

from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import metadata_models as m


def configure_authorities(f):
    with f["sf"]() as session, session.begin():
        run = session.scalar(
            select(c.ContextResolutionRunEntity).where(
                c.ContextResolutionRunEntity.project_id == f["project"],
                c.ContextResolutionRunEntity.tenant_id == f["tenant"],
            )
        )
        for role in ("SOURCE", "DESTINATION"):
            session.add(
                c.JurisdictionContextEntity(
                    jurisdiction_context_id=str(uuid4()),
                    tenant_id=f["tenant"],
                    project_id=f["project"],
                    jurisdiction_id=f["juri"],
                    context_type=role,
                    location_precision="COUNTRY",
                    source="APPROVED_METADATA",
                    confidence=1,
                    validation_status="VALIDATED",
                    version=run.version,
                )
            )
        ob = f["j_policies"]["OBLIGATION_POLICY"]
        entry = session.get(m.MetadataVersionEntity, ob["version_id"]).payload_json["entries"][0][
            "entry_id"
        ]
    cross = publish_config(
        f,
        "CROSS_BORDER_ASSESSMENT_POLICY",
        dict(
            jurisdiction_ids=[f["juri"]],
            obligation_policy_id=ob["definition_id"],
            transfer_legally_possible=dict(
                entry_id=str(uuid4()),
                code="GOVERNED_TEST_PERMISSION",
                fields=[dict(code="count", field_type=dict(kind="integer"))],
                predicate='{"op":"gte","field":"count","value":1}',
                examples=[dict(facts=[dict(code="count", value=3)], expected="TRUE")],
            ),
            prerequisites=[],
        ),
    )
    publish_config(
        f,
        "DOCUMENT_REQUIREMENT_POLICY",
        dict(
            jurisdiction_ids=[f["juri"]],
            obligation_policy_id=ob["definition_id"],
            cross_border_policy_id=cross["definition_id"],
            entries=[
                dict(
                    entry_id=str(uuid4()),
                    document_type_code="GOVERNED_DOCUMENT",
                    name="Governed test requirement",
                    requirement_level="REQUIRED",
                    trigger_obligation_entry_ids=[entry],
                )
            ],
        ),
    )

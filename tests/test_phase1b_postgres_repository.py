from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.entities import (
    ClassificationResult,
    ConversationThread,
    EvidenceReference,
    Jurisdiction,
    LegalBasisItem,
    Project,
    ProjectVersion,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.models import (
    ChannelContextEntity,
    ClassificationCategoryEntity,
    ClassificationLevelEntity,
    ClassificationResultCategoryEntity,
    ClassificationSchemeEntity,
    InteractionSessionEntity,
    LegalBasisEvidenceLinkEntity,
    LegalBasisRuleHitLinkEntity,
    ProjectEntity,
    ProjectVersionEntity,
    RuleHitEntity,
    TenantEntity,
)
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    OptimisticConcurrencyError,
    PostgresClassificationRepository,
    PostgresConversationRepository,
    PostgresEvidenceRepository,
    PostgresJurisdictionRepository,
    PostgresLegalBasisRepository,
    PostgresProjectRepository,
)


def _postgres_session_factory():
    settings = get_settings()
    if not settings.database_url.startswith("postgresql"):
        pytest.skip("Phase 1B repository integration requires real PostgreSQL")
    return build_session_factory(settings.database_url)[1]


def _seed_tenant(session_factory, tenant_id, name: str) -> None:
    with session_factory() as session, session.begin():
        session.add(TenantEntity(tenant_id=str(tenant_id), name=name))


def _project_repo(session_factory, tenant_id):
    return PostgresProjectRepository(
        session_factory,
        RepositoryContext.user(tenant_id, actor_id=f"user-{tenant_id}"),
    )


def test_postgres_crud_tenant_isolation_uuid_guessing_and_explicit_system_context() -> None:
    sf = _postgres_session_factory()
    tenant_a, tenant_b = uuid4(), uuid4()
    _seed_tenant(sf, tenant_a, "Tenant A")
    _seed_tenant(sf, tenant_b, "Tenant B")

    repo_a = _project_repo(sf, tenant_a)
    repo_b = _project_repo(sf, tenant_b)
    project_a = Project(tenant_id=tenant_a, project_id=uuid4(), name=f"A-{uuid4()}")
    project_b = Project(tenant_id=tenant_b, project_id=uuid4(), name=f"B-{uuid4()}")
    repo_a.add_project(project_a)
    repo_b.add_project(project_b)

    assert repo_a.get_project(project_a.project_id) is not None
    assert repo_a.get_project(project_b.project_id) is None
    assert repo_b.get_project(project_a.project_id) is None

    version_b = ProjectVersion(
        tenant_id=tenant_b,
        project_version_id=uuid4(),
        project_id=project_b.project_id,
        version_no=1,
        intake_json={"source": "tenant-b"},
    )
    repo_b.add_version(version_b)
    with pytest.raises(LookupError):
        repo_a.activate_version(project_b.project_id, version_b.project_version_id, expected_record_version=1)

    system_b = PostgresProjectRepository(sf, RepositoryContext.system(tenant_b))
    assert system_b.get_project(project_b.project_id) is not None
    assert system_b.get_project(project_a.project_id) is None


def test_immutable_project_version_active_pointer_and_optimistic_concurrency() -> None:
    sf = _postgres_session_factory()
    tenant = uuid4()
    _seed_tenant(sf, tenant, "Version Tenant")
    repo = _project_repo(sf, tenant)
    project = Project(tenant_id=tenant, project_id=uuid4(), name=f"Versioned-{uuid4()}")
    repo.add_project(project)

    v1 = ProjectVersion(
        tenant_id=tenant,
        project_version_id=uuid4(),
        project_id=project.project_id,
        version_no=1,
        intake_json={"version": 1},
    )
    repo.add_version(v1)
    activated = repo.activate_version(project.project_id, v1.project_version_id, expected_record_version=1)
    assert activated.active_version_id == v1.project_version_id
    assert activated.record_version == 2

    with pytest.raises(OptimisticConcurrencyError):
        repo.activate_version(project.project_id, v1.project_version_id, expected_record_version=1)

    with sf() as session:
        persisted = session.scalar(
            select(ProjectVersionEntity).where(
                ProjectVersionEntity.project_version_id == str(v1.project_version_id)
            )
        )
        assert persisted is not None
        assert persisted.intake_json == {"version": 1}


def test_unique_constraint_fk_and_transaction_rollback() -> None:
    sf = _postgres_session_factory()
    tenant = uuid4()
    _seed_tenant(sf, tenant, "Constraint Tenant")
    repo = _project_repo(sf, tenant)
    name = f"Unique-{uuid4()}"
    repo.add_project(Project(tenant_id=tenant, project_id=uuid4(), name=name))
    with pytest.raises(IntegrityError):
        repo.add_project(Project(tenant_id=tenant, project_id=uuid4(), name=name))

    with pytest.raises(IntegrityError):
        with sf() as session, session.begin():
            session.add(
                ProjectVersionEntity(
                    project_version_id=str(uuid4()),
                    tenant_id=str(tenant),
                    project_id=str(uuid4()),
                    version_no=1,
                    intake_json={},
                )
            )

    rolled_back_project_id = uuid4()
    session = sf()
    try:
        session.add(
            ProjectEntity(
                project_id=str(rolled_back_project_id),
                tenant_id=str(tenant),
                name=f"Rollback-{uuid4()}",
            )
        )
        session.flush()
        session.rollback()
    finally:
        session.close()
    assert repo.get_project(rolled_back_project_id) is None


def test_classification_repository_is_single_formal_result_source() -> None:
    sf = _postgres_session_factory()
    tenant = uuid4()
    _seed_tenant(sf, tenant, "Classification Tenant")

    jurisdiction = Jurisdiction(
        tenant_id=tenant,
        jurisdiction_id=uuid4(),
        code=f"J-{uuid4().hex[:8]}",
        name="Test Jurisdiction",
    )
    PostgresJurisdictionRepository(sf, RepositoryContext.user(tenant, "classifier")).add_jurisdiction(
        jurisdiction
    )

    scheme_id, category_id, level_id = uuid4(), uuid4(), uuid4()
    with sf() as session, session.begin():
        session.add(
            ClassificationSchemeEntity(
                scheme_id=str(scheme_id),
                tenant_id=str(tenant),
                code=f"SCHEME-{uuid4().hex[:8]}",
                name="Generic Scheme",
            )
        )
        # No ORM relationship is declared intentionally; flush the FK parent explicitly.
        session.flush()
        session.add(
            ClassificationCategoryEntity(
                category_id=str(category_id),
                tenant_id=str(tenant),
                scheme_id=str(scheme_id),
                code="GENERIC",
                name="Generic Category",
            )
        )
        session.add(
            ClassificationLevelEntity(
                level_id=str(level_id),
                tenant_id=str(tenant),
                scheme_id=str(scheme_id),
                code="L1",
                rank=1,
            )
        )

    result = ClassificationResult(
        tenant_id=tenant,
        classification_result_id=uuid4(),
        subject_type="DATA_ITEM",
        subject_id=uuid4(),
        scheme_id=scheme_id,
        level_id=level_id,
        jurisdiction_id=jurisdiction.jurisdiction_id,
        confidence=0.9,
        review_required=False,
    )
    repo = PostgresClassificationRepository(sf, RepositoryContext.user(tenant, "classifier"))
    repo.add_result(result, [category_id])
    loaded = repo.get_result(result.classification_result_id)
    assert loaded is not None and loaded.classification_result_id == result.classification_result_id

    with sf() as session:
        link_count = session.scalar(
            select(func.count())
            .select_from(ClassificationResultCategoryEntity)
            .where(
                ClassificationResultCategoryEntity.classification_result_id
                == str(result.classification_result_id)
            )
        )
        assert link_count == 1


def test_legal_basis_rule_hit_many_to_many_and_cross_tenant_link_rejected() -> None:
    sf = _postgres_session_factory()
    tenant_a, tenant_b = uuid4(), uuid4()
    _seed_tenant(sf, tenant_a, "Legal A")
    _seed_tenant(sf, tenant_b, "Legal B")

    jurisdiction = Jurisdiction(
        tenant_id=tenant_a,
        jurisdiction_id=uuid4(),
        code=f"JA-{uuid4().hex[:8]}",
        name="Legal Jurisdiction",
    )
    PostgresJurisdictionRepository(sf, RepositoryContext.user(tenant_a, "legal")).add_jurisdiction(
        jurisdiction
    )

    hit_1, hit_2, hit_cross = uuid4(), uuid4(), uuid4()
    with sf() as session, session.begin():
        session.add_all(
            [
                RuleHitEntity(
                    rule_hit_id=str(hit_1),
                    tenant_id=str(tenant_a),
                    rule_version_ref="generic-rule-v1",
                    subject_type="DATA_ITEM",
                    subject_id=str(uuid4()),
                    evidence_json={},
                ),
                RuleHitEntity(
                    rule_hit_id=str(hit_2),
                    tenant_id=str(tenant_a),
                    rule_version_ref="generic-rule-v2",
                    subject_type="DATA_ITEM",
                    subject_id=str(uuid4()),
                    evidence_json={},
                ),
                RuleHitEntity(
                    rule_hit_id=str(hit_cross),
                    tenant_id=str(tenant_b),
                    rule_version_ref="generic-rule-cross",
                    subject_type="DATA_ITEM",
                    subject_id=str(uuid4()),
                    evidence_json={},
                ),
            ]
        )

    evidence = EvidenceReference(
        tenant_id=tenant_a,
        evidence_id=uuid4(),
        evidence_type="SOURCE_TRACE",
        source_ref=f"source:{uuid4()}",
        validation_status="VALID",
    )
    PostgresEvidenceRepository(sf, RepositoryContext.user(tenant_a, "legal")).add_evidence(evidence)

    legal_basis = LegalBasisItem(
        tenant_id=tenant_a,
        legal_basis_id=uuid4(),
        jurisdiction_id=jurisdiction.jurisdiction_id,
        legal_basis_summary="Generic legal basis persistence test",
        applicability_reason="Foundation relation test",
        official_source="official-source-ref",
        citation_locator="section:test",
    )
    repo = PostgresLegalBasisRepository(sf, RepositoryContext.user(tenant_a, "legal"))
    repo.add_legal_basis(legal_basis)
    repo.link_rule_hit(legal_basis.legal_basis_id, hit_1)
    repo.link_rule_hit(legal_basis.legal_basis_id, hit_2)
    repo.link_evidence(legal_basis.legal_basis_id, evidence.evidence_id)

    with pytest.raises(LookupError):
        repo.link_rule_hit(legal_basis.legal_basis_id, hit_cross)

    with sf() as session:
        rule_links = session.scalar(
            select(func.count())
            .select_from(LegalBasisRuleHitLinkEntity)
            .where(LegalBasisRuleHitLinkEntity.legal_basis_id == str(legal_basis.legal_basis_id))
        )
        evidence_links = session.scalar(
            select(func.count())
            .select_from(LegalBasisEvidenceLinkEntity)
            .where(LegalBasisEvidenceLinkEntity.legal_basis_id == str(legal_basis.legal_basis_id))
        )
        assert rule_links == 2
        assert evidence_links == 1


def test_conversation_repository_is_tenant_scoped_and_not_workflow_thread_id() -> None:
    sf = _postgres_session_factory()
    tenant_a, tenant_b = uuid4(), uuid4()
    _seed_tenant(sf, tenant_a, "Conversation A")
    _seed_tenant(sf, tenant_b, "Conversation B")
    channel_id, session_id = uuid4(), uuid4()

    with sf() as session, session.begin():
        session.add(
            ChannelContextEntity(
                channel_context_id=str(channel_id),
                tenant_id=str(tenant_a),
                channel_type="WEB",
                request_id=f"req-{uuid4()}",
            )
        )
        session.add(
            InteractionSessionEntity(
                session_id=str(session_id),
                tenant_id=str(tenant_a),
                channel_context_id=str(channel_id),
            )
        )

    thread = ConversationThread(
        tenant_id=tenant_a,
        conversation_thread_id=uuid4(),
        session_id=session_id,
        title="Phase 1B conversation",
    )
    repo_a = PostgresConversationRepository(sf, RepositoryContext.user(tenant_a, "user-a"))
    repo_b = PostgresConversationRepository(sf, RepositoryContext.user(tenant_b, "user-b"))
    repo_a.add_thread(thread)
    assert repo_a.get_thread(thread.conversation_thread_id) is not None
    assert repo_b.get_thread(thread.conversation_thread_id) is None

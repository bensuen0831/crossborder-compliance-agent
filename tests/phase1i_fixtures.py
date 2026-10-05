from datetime import date
from uuid import uuid4

from phase1h_fixtures import domain_fixture

from crossborder_compliance.domain.classification import classify
from crossborder_compliance.domain.compliance_profiles import (
    ApplicabilityConfig,
    CountryComplianceProfile,
    CountryProfileConfig,
    ScenarioExecutionConfiguration,
)
from crossborder_compliance.domain.regulation_applicability import (
    ApplicabilityInput,
    CanonicalLegalReference,
)
from crossborder_compliance.domain.retrieval import KnowledgeSufficiencyResult
from crossborder_compliance.domain.rules import SafeRuleEngine


def prepared():
    r, context, scheme = domain_fixture()
    hits = SafeRuleEngine().evaluate((r,), context, pinned_versions=frozenset({r.rule_version_id}))
    classification = classify(scheme, context, hits).result
    version = uuid4()
    node = uuid4()
    basis = uuid4()
    pack = uuid4()
    profile = uuid4()
    scenario = uuid4()
    config = ApplicabilityConfig(
        jurisdiction_id=context.jurisdiction_id,
        knowledge_version_id=version,
        regulatory_structure_node_ids=(node,),
        legal_basis_ids=(basis,),
        required_rule_ids=(r.rule_id,),
        reason_code="CONFIGURED_RULE_DECISION",
        effective_from=date(2025, 1, 1),
    )
    country = CountryComplianceProfile(
        profile_id=profile,
        version_id=uuid4(),
        tenant_id=context.tenant_id,
        version=1,
        lifecycle="ACTIVE",
        provenance={"approved_by": "independent-reviewer"},
        config=CountryProfileConfig(
            jurisdiction_id=context.jurisdiction_id, effective_from=date(2025, 1, 1)
        ),
    )
    suff = KnowledgeSufficiencyResult(
        sufficiency_result_id=str(uuid4()),
        tenant_id=str(context.tenant_id),
        project_id=str(context.project_id),
        analysis_snapshot_id=str(context.analysis_snapshot_id),
        subject_type="DATA_ITEM",
        subject_id=str(context.data_item_id),
        jurisdiction_ids=(str(context.jurisdiction_id),),
        retrieval_run_id=str(uuid4()),
        evidence_pack_id=str(pack),
        jurisdiction_coverage={str(context.jurisdiction_id): True},
        regulation_coverage={str(version): True},
        official_source_coverage=1,
        effective_date_coverage=1,
        evidence_quality=1,
        evidence_count=1,
        conflicting_evidence_count=0,
        missing_topics=(),
        reason_codes=("SUFFICIENT",),
        confidence=0.95,
        review_required=False,
        status="SUFFICIENT",
        policy_version=str(uuid4()),
    )
    return ApplicabilityInput(
        tenant_id=context.tenant_id,
        project_id=context.project_id,
        analysis_snapshot_id=context.analysis_snapshot_id,
        subject_type="DATA_ITEM",
        subject_id=context.data_item_id,
        data_item_ids=(context.data_item_id,),
        scenario_definition_ids=(scenario,),
        jurisdiction_id=context.jurisdiction_id,
        analysis_as_of_date=date(2026, 1, 1),
        context_version=context.context_version,
        fact_refs=tuple(context.fact_refs["count"]),
        country_profile=country,
        scenario_configuration=ScenarioExecutionConfiguration(status="READY"),
        applicability_config_id=uuid4(),
        applicability_config_version_id=uuid4(),
        applicability_config_version=1,
        config=config,
        canonical_legal_reference=CanonicalLegalReference(
            knowledge_document_id=uuid4(),
            knowledge_version_id=version,
            jurisdiction_id=context.jurisdiction_id,
            regulatory_structure_node_ids=(node,),
            legal_basis_ids=(basis,),
            evidence_ids=context.evidence_ids,
            official_sources=("https://official.example/regulation",),
            citation_locators=("article/1",),
            effective_from=date(2025, 1, 1),
            effective_to=None,
            validation_status="VALIDATED",
        ),
        classifications=(classification,),
        rule_hits=hits,
        evidence_ids=context.evidence_ids,
        evidence_pack_ids=(pack,),
        sufficiency=suff,
    )

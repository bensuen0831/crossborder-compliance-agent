"""Authorized adapters over existing context, registry pins, classification and retrieval."""

from uuid import UUID, uuid4

from sqlalchemy import select

from crossborder_compliance.infrastructure.persistence.context_temporal import exact_item_detail, flow_item_ids

from crossborder_compliance.application.country_compliance_services import (
    ApplicabilityRequest,
    CountryProfileResolution,
)
from crossborder_compliance.application.knowledge_services import KnowledgeScopeResolver
from crossborder_compliance.domain.classification import ClassificationResult
from crossborder_compliance.domain.compliance_profiles import (
    CONFIG_TYPES,
    CountryCapability,
    CountryComplianceProfile,
    ScenarioAdjustmentProfile,
    effective,
    merge_scenario_profiles,
)
from crossborder_compliance.domain.regulation_applicability import (
    ApplicabilityInput,
    CanonicalLegalReference,
    RegulationApplicabilityResult,
)
from crossborder_compliance.domain.retrieval import RAGContextPack
from crossborder_compliance.domain.rules import RuleHit
from crossborder_compliance.infrastructure.persistence import applicability_models as i
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence import retrieval_models as g
from crossborder_compliance.infrastructure.persistence.classification_repository import (
    PostgresFormalClassificationRepository,
)
from crossborder_compliance.infrastructure.persistence.compliance_profile_governance import scoped
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import hash_value
from crossborder_compliance.infrastructure.persistence.retrieval_repositories import (
    PostgresRetrievalRepository,
)


class PostgresCountryComplianceRepository:
    def initialize_formal_results(self, project_id, snapshot_id):
        from crossborder_compliance.infrastructure.persistence.formal_result_repository import initialize
        return initialize(self, project_id, snapshot_id)

    def prepare_formal_result(self, request):
        from crossborder_compliance.infrastructure.persistence.formal_result_repository import prepare
        return prepare(self, request)

    def save_formal_result(self, request, result):
        from crossborder_compliance.infrastructure.persistence.formal_result_repository import save
        return save(self, request, result)

    def read_formal_result(self, kind, ident):
        from crossborder_compliance.infrastructure.persistence.formal_result_repository import read
        return read(self, kind, ident)

    def initialize_decisions(self, project_id, snapshot_id):
        # Historical J snapshots keep their original sealed dependency universe.
        # New snapshots capture C0 before J; C0 never retrofits a historical pin.
        with self.sessions() as session:
            from crossborder_compliance.infrastructure.persistence.decision_repository import pins
            sealed = any(p.pin_type == 'PHASE1J_INITIALIZATION' for p in pins(self, session, snapshot_id))
        if not sealed:
            self.initialize_formal_results(project_id, snapshot_id)
        from crossborder_compliance.infrastructure.persistence.decision_repository import initialize
        return initialize(self, project_id, snapshot_id)

    def prepare_decision(self, request):
        from crossborder_compliance.infrastructure.persistence.decision_repository import prepare
        return prepare(self, request)

    def save_decision(self, request, result):
        from crossborder_compliance.infrastructure.persistence.decision_repository import save
        return save(self, request, result)

    def read_decision(self, stage, ident):
        from crossborder_compliance.infrastructure.persistence.decision_repository import read
        return read(self, stage, ident)

    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context
        self.tenant = str(context.tenant_id)
        self.retrieval = PostgresRetrievalRepository(sessions, context)
        self.classifier = PostgresFormalClassificationRepository(sessions, context)

    def authorize(self, project_id, operation="execute"):
        if not self.context.permission.system and (
            f"applicability:{operation}" not in self.context.permission.scopes
            or f"project:{project_id}:comply" not in self.context.permission.scopes
        ):
            raise LookupError("compliance resource not found")

    def get(self, s, model, ident):
        return scoped(s, model, ident, self.tenant)

    def snapshot(self, s, project_id, snapshot_id, lock=False, operation="execute"):
        self.authorize(project_id, operation)
        query = select(b.AnalysisSnapshotEntity).where(
            b.AnalysisSnapshotEntity.tenant_id == self.tenant,
            b.AnalysisSnapshotEntity.analysis_snapshot_id == str(snapshot_id),
        )
        snapshot = s.scalar(query.with_for_update() if lock else query)
        if snapshot is None:
            raise LookupError("compliance resource not found")
        version = self.get(s, b.ProjectVersionEntity, snapshot.project_version_id)
        if version.project_id != str(project_id):
            raise LookupError("compliance resource not found")
        pin = s.scalar(
            select(c.AnalysisSnapshotContextPinEntity).where(
                c.AnalysisSnapshotContextPinEntity.tenant_id == self.tenant,
                c.AnalysisSnapshotContextPinEntity.analysis_snapshot_id == str(snapshot_id),
                c.AnalysisSnapshotContextPinEntity.project_id == str(project_id),
            )
        )
        if pin is None:
            raise ValueError("Phase1I requires explicit formal context pins")
        return snapshot, pin

    def formal(self, project_id, snapshot_id, jurisdiction_id, operation="execute"):
        with self.sessions() as s:
            snapshot, pin = self.snapshot(s, project_id, snapshot_id, operation=operation)
            scenarios = s.scalars(
                select(c.ScenarioContextEntity).where(
                    c.ScenarioContextEntity.tenant_id == self.tenant,
                    c.ScenarioContextEntity.project_id == str(project_id),
                    c.ScenarioContextEntity.version == pin.context_resolution_version,
                    c.ScenarioContextEntity.validation_status == "VALIDATED",
                    c.ScenarioContextEntity.review_required.is_(False),
                )
            ).all()
            jurisdictions = s.scalars(
                select(c.JurisdictionContextEntity).where(
                    c.JurisdictionContextEntity.tenant_id == self.tenant,
                    c.JurisdictionContextEntity.project_id == str(project_id),
                    c.JurisdictionContextEntity.version == pin.context_resolution_version,
                    c.JurisdictionContextEntity.validation_status == "VALIDATED",
                    c.JurisdictionContextEntity.review_required.is_(False),
                )
            ).all()
            if str(jurisdiction_id) not in {v.jurisdiction_id for v in jurisdictions}:
                raise LookupError("jurisdiction not in pinned formal context")
            facts = s.scalars(
                select(c.BusinessFactEntity).where(
                    c.BusinessFactEntity.tenant_id == self.tenant,
                    c.BusinessFactEntity.project_id == str(project_id),
                    c.BusinessFactEntity.version == pin.context_resolution_version,
                    c.BusinessFactEntity.validation_status == "VALIDATED",
                    c.BusinessFactEntity.review_required.is_(False),
                )
            ).all()
            inputs = frozenset(
                [
                    "FORMAL_CONTEXT",
                    "JURISDICTION",
                    *(["SCENARIO"] if scenarios else []),
                    *[f.fact_type for f in facts],
                ]
            )
            return (
                snapshot,
                pin,
                tuple(
                    UUID(v.scenario_definition_id) for v in scenarios if v.scenario_definition_id
                ),
                facts,
                inputs,
            )

    def active_configs(self, s, kind, when):
        pairs = s.execute(
            select(m.MetadataDefinitionEntity, m.MetadataVersionEntity)
            .join(
                m.MetadataVersionEntity,
                m.MetadataDefinitionEntity.active_version_id == m.MetadataVersionEntity.version_id,
            )
            .where(
                m.MetadataDefinitionEntity.tenant_id == self.tenant,
                m.MetadataVersionEntity.tenant_id == self.tenant,
                m.MetadataDefinitionEntity.kind == kind,
                m.MetadataDefinitionEntity.status == "ACTIVE",
                m.MetadataVersionEntity.lifecycle_status == "ACTIVE",
            )
        ).all()
        result = []
        for definition, version in pairs:
            config = CONFIG_TYPES[kind].model_validate(version.payload_json)
            if (
                not self.context.permission.system
                and not set(getattr(config, "permission_scopes", ()))
                <= self.context.permission.scopes
            ):
                continue
            if version.approved_by and version.published_at and effective(config, when):
                result.append((definition, version, config))
        return sorted(result, key=lambda p: str(p[0].definition_id))

    def pins(self, s, snapshot_id):
        return s.scalars(
            select(m.AnalysisSnapshotRegistryPinEntity).where(
                m.AnalysisSnapshotRegistryPinEntity.tenant_id == self.tenant,
                m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == str(snapshot_id),
                m.AnalysisSnapshotRegistryPinEntity.pin_type.like("PHASE1I_%"),
            )
        ).all()

    def add_pin(self, s, snapshot_id, kind, logical, object_id, version_id, version):
        current = [
            p
            for p in self.pins(s, snapshot_id)
            if p.pin_type == f"PHASE1I_{kind}" and p.logical_key == str(logical)
        ]
        if current:
            if current[0].version_id != str(version_id):
                raise ValueError("immutable Phase1I pin mismatch")
            return
        s.add(
            m.AnalysisSnapshotRegistryPinEntity(
                pin_id=str(uuid4()),
                tenant_id=self.tenant,
                analysis_snapshot_id=str(snapshot_id),
                pin_type=f"PHASE1I_{kind}",
                logical_key=str(logical),
                object_id=str(object_id),
                version_id=str(version_id),
                version_no=version,
            )
        )
        s.flush()

    def initialize(self, project_id, snapshot_id, jurisdiction_id):
        snapshot, _, scenarios, _, _ = self.formal(project_id, snapshot_id, jurisdiction_id)
        with self.sessions() as s, s.begin():
            self.snapshot(s, project_id, snapshot_id, True)
            if any(
                p.pin_type == "PHASE1I_CONFIGURATION" and p.logical_key == str(jurisdiction_id)
                for p in self.pins(s, snapshot_id)
            ):
                return {
                    "status": "PINNED",
                    "pins": [p.version_id for p in self.pins(s, snapshot_id)],
                }
            country = [
                p
                for p in self.active_configs(s, "COUNTRY_PROFILE", snapshot.analysis_as_of_date)
                if p[2].jurisdiction_id == jurisdiction_id
            ]
            adjustments = [
                p
                for p in self.active_configs(s, "SCENARIO_ADJUSTMENT", snapshot.analysis_as_of_date)
                if p[2].scenario_definition_id in scenarios
            ]
            configs = [
                p
                for p in self.active_configs(
                    s, "APPLICABILITY_CONFIG", snapshot.analysis_as_of_date
                )
                if p[2].jurisdiction_id == jurisdiction_id
            ]
            # Applicability refs in a country profile are constraints on eligible configs.
            allowed_configs = {ident for p in country for ident in p[2].applicability_config_ids}
            if country:
                configs = [p for p in configs if UUID(p[0].definition_id) in allowed_configs]
            selected = [*country, *adjustments, *configs]
            dependencies = {"COUNTRY_CAPABILITY": set(), "RULE_PACK": set()}
            for _, _, config in selected:
                dependencies["COUNTRY_CAPABILITY"].update(getattr(config, "capability_ids", ()))
                dependencies["COUNTRY_CAPABILITY"].update(
                    getattr(config, "required_country_capability_ids", ())
                )
                dependencies["RULE_PACK"].update(getattr(config, "rule_pack_ids", ()))
            for kind, identifiers in dependencies.items():
                if kind == "RULE_PACK":
                    identifiers.update(
                        ident
                        for _, _, config in selected
                        for ident in getattr(config, "rule_pack_ids", ())
                    )
                available = self.active_configs(s, kind, snapshot.analysis_as_of_date)
                selected.extend(p for p in available if UUID(p[0].definition_id) in identifiers)
            for _, _, config in selected:
                for kind, model, identifiers in self.resource_references(config):
                    for ident in identifiers:
                        resource = self.validate_resource(
                            s, model, ident, snapshot.analysis_as_of_date
                        )
                        self.add_pin(s, snapshot_id, kind, ident, ident, ident, resource.version_no)
            for definition, version, config in selected:
                if (
                    hasattr(config, "permission_scopes")
                    and not self.context.permission.system
                    and not set(config.permission_scopes) <= self.context.permission.scopes
                ):
                    raise LookupError("country profile not authorized")
                self.add_pin(
                    s,
                    snapshot_id,
                    definition.kind,
                    definition.definition_id,
                    definition.definition_id,
                    version.version_id,
                    version.version_no,
                )
                if definition.kind == "APPLICABILITY_CONFIG":
                    legal = self.get(
                        s, k.KnowledgeDocumentVersionEntity, config.knowledge_version_id
                    )
                    readiness = s.scalar(
                        select(g.KnowledgeRuntimePublicationEntity).where(
                            g.KnowledgeRuntimePublicationEntity.tenant_id == self.tenant,
                            g.KnowledgeRuntimePublicationEntity.knowledge_version_id
                            == str(config.knowledge_version_id),
                            g.KnowledgeRuntimePublicationEntity.status == "READY",
                        )
                    )
                    scopes = s.scalars(
                        select(k.KnowledgeScopeResolutionEntity).where(
                            k.KnowledgeScopeResolutionEntity.tenant_id == self.tenant,
                            k.KnowledgeScopeResolutionEntity.analysis_snapshot_id
                            == str(snapshot_id),
                        )
                    ).all()
                    resolver = KnowledgeScopeResolver(self.retrieval, self.context)
                    universe = {
                        v
                        for scope in scopes
                        if scope.project_id == str(project_id)
                        for v in resolver.resolve(
                            str(project_id),
                            subject_type=scope.subject_type,
                            subject_id=scope.subject_id,
                            snapshot_id=str(snapshot_id),
                        ).filter_spec.version_filter
                    }
                    if (
                        legal.lifecycle != "ACTIVE"
                        or readiness is None
                        or not self.date_valid(legal, snapshot.analysis_as_of_date)
                        or str(config.knowledge_version_id) not in universe
                    ):
                        raise ValueError(
                            "new applicability pin requires authorized effective ACTIVE READY"
                            " knowledge"
                            " already in snapshot scope"
                        )
                    self.add_pin(
                        s,
                        snapshot_id,
                        "KNOWLEDGE",
                        legal.document_id,
                        legal.document_id,
                        legal.knowledge_version_id,
                        legal.version,
                    )
            skill_ids = {
                ident
                for _, _, config in adjustments
                for ident in (
                    *config.required_skill_ids,
                    *config.disabled_skill_ids,
                    *(condition.skill_id for condition in config.conditional_skill_ids),
                )
            }
            for ident in sorted(skill_ids, key=str):
                definition = self.get(s, m.MetadataDefinitionEntity, ident)
                version = self.get(s, m.MetadataVersionEntity, definition.active_version_id)
                if (
                    definition.kind != "SKILL"
                    or definition.status != "ACTIVE"
                    or version.lifecycle_status != "ACTIVE"
                    or not version.approved_by
                    or not version.published_at
                    or not self.date_valid(version, snapshot.analysis_as_of_date)
                ):
                    raise ValueError(
                        "scenario skills require published effective ACTIVE registry versions"
                    )
                self.add_pin(
                    s, snapshot_id, "SKILL", ident, ident, version.version_id, version.version_no
                )
            for _, _, config in adjustments:
                for kind, model, identifiers in (
                    (
                        "KNOWLEDGE_BINDING",
                        m.KnowledgeBindingEntity,
                        config.knowledge_scope_bindings,
                    ),
                    ("RULE_BINDING", m.RuleBindingEntity, config.rule_scope_bindings),
                    ("TEMPLATE_BINDING", m.TemplateBindingEntity, config.template_scope_bindings),
                ):
                    for ident in identifiers:
                        binding = self.get(s, model, ident)
                        if kind == "TEMPLATE_BINDING":
                            resource = self.validate_resource(
                                s,
                                m.TemplateVersionEntity,
                                binding.template_version_id,
                                snapshot.analysis_as_of_date,
                            )
                            self.add_pin(
                                s,
                                snapshot_id,
                                "TEMPLATE",
                                resource.template_version_id,
                                resource.template_version_id,
                                resource.template_version_id,
                                resource.version_no,
                            )
                        payload = {
                            col.name: str(getattr(binding, col.name))
                            for col in model.__table__.columns
                        }
                        self.add_pin(
                            s,
                            snapshot_id,
                            kind,
                            str(ident) + ":" + hash_value(payload),
                            ident,
                            ident,
                            binding.record_version,
                        )
            self.add_pin(
                s, snapshot_id, "CONFIGURATION", jurisdiction_id, snapshot_id, snapshot_id, 1
            )
            return {"status": "PINNED", "pins": [p.version_id for p in self.pins(s, snapshot_id)]}

    @staticmethod
    def resource_references(config):
        return (
            ("PROMPT", m.PromptVersionEntity, getattr(config, "prompt_config_ids", ())),
            ("TEMPLATE", m.TemplateVersionEntity, getattr(config, "template_scope_ids", ())),
        )

    def validate_resource(self, session, model, ident, when, historical=False):
        resource = self.get(session, model, ident)
        states = {"ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"} if historical else {"ACTIVE"}
        if resource.lifecycle_status not in states or not self.date_valid(resource, when):
            raise ValueError("profile resource requires a published effective version")
        kind = "PROMPT" if model is m.PromptVersionEntity else "TEMPLATE"
        if not session.scalar(
            select(m.AdminPublishRecordEntity).where(
                m.AdminPublishRecordEntity.tenant_id == self.tenant,
                m.AdminPublishRecordEntity.object_kind == kind,
                m.AdminPublishRecordEntity.version_id == str(ident),
            )
        ):
            raise ValueError("profile resource requires durable publication provenance")
        return resource

    def validate_resource_pins(self, session, config, pins, when):
        for kind, model, identifiers in self.resource_references(config):
            for ident in identifiers:
                resource = self.validate_resource(session, model, ident, when, historical=True)
                if not any(
                    p.pin_type == "PHASE1I_" + kind
                    and p.version_id == str(ident)
                    and p.version_no == resource.version_no
                    for p in pins
                ):
                    raise LookupError("profile resource is not snapshot pinned")

    @staticmethod
    def date_valid(row, when):
        return (row.effective_from is None or row.effective_from <= when) and (
            row.effective_to is None or row.effective_to >= when
        )

    def published(self, s, pin, kind, when):
        definition = self.get(s, m.MetadataDefinitionEntity, pin.object_id)
        row = self.get(s, m.MetadataVersionEntity, pin.version_id)
        if (
            definition.kind != kind
            or row.definition_id != pin.object_id
            or row.version_no != pin.version_no
            or row.lifecycle_status not in {"ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"}
            or not row.approved_by
            or not row.published_at
        ):
            raise ValueError("invalid published snapshot profile")
        config = CONFIG_TYPES[kind].model_validate(row.payload_json)
        if not effective(config, when):
            raise ValueError("profile ineffective at analysis date")
        if (
            hasattr(config, "permission_scopes")
            and not self.context.permission.system
            and not set(config.permission_scopes) <= self.context.permission.scopes
        ):
            raise LookupError("country profile not authorized")
        return row, config

    def envelope(self, row, config):
        return {
            "profile_id": row.definition_id,
            "version_id": row.version_id,
            "tenant_id": row.tenant_id,
            "version": row.version_no,
            "lifecycle": row.lifecycle_status,
            "provenance": {
                "approved_by": row.approved_by,
                "published_at": row.published_at.isoformat(),
            },
            "config": config,
        }

    def resolve_profile(self, project_id, snapshot_id, jurisdiction_id, operation="execute"):
        snapshot, _, scenarios, _, inputs = self.formal(
            project_id, snapshot_id, jurisdiction_id, operation
        )
        with self.sessions() as s:
            pins = self.pins(s, snapshot_id)
            if not any(
                p.pin_type == "PHASE1I_CONFIGURATION" and p.logical_key == str(jurisdiction_id)
                for p in pins
            ):
                raise ValueError("Phase1I configuration must be explicitly initialized")
            profiles = []
            adjustments = []
            capabilities = []
            for pin in pins:
                kind = pin.pin_type.removeprefix("PHASE1I_")
                if kind not in {"COUNTRY_PROFILE", "SCENARIO_ADJUSTMENT", "COUNTRY_CAPABILITY"}:
                    continue
                row, config = self.published(s, pin, kind, snapshot.analysis_as_of_date)
                self.validate_resource_pins(s, config, pins, snapshot.analysis_as_of_date)
                if kind == "COUNTRY_PROFILE" and config.jurisdiction_id == jurisdiction_id:
                    profiles.append(CountryComplianceProfile(**self.envelope(row, config)))
                elif kind == "SCENARIO_ADJUSTMENT" and config.scenario_definition_id in scenarios:
                    adjustments.append(ScenarioAdjustmentProfile(**self.envelope(row, config)))
                elif kind == "COUNTRY_CAPABILITY":
                    capabilities.append(CountryCapability(**self.envelope(row, config)))
        merged = merge_scenario_profiles(tuple(adjustments), inputs)
        status = (
            "CONFLICTED"
            if len(profiles) > 1 or merged.conflict_codes
            else "READY"
            if profiles and merged.status == "READY"
            else "REVIEW_REQUIRED"
        )
        required = set(merged.required_country_capability_ids)
        if len(profiles) == 1 and (
            not required <= set(profiles[0].config.capability_ids)
            or not required <= {c.profile_id for c in capabilities}
            or not set(profiles[0].config.capability_ids) <= {c.profile_id for c in capabilities}
        ):
            status = "REVIEW_REQUIRED"
        return CountryProfileResolution(
            status=status,
            profiles=tuple(profiles),
            capabilities=tuple(capabilities),
            scenario_configuration=merged,
            reason_codes=(
                "COUNTRY_PROFILE_CONFLICT"
                if len(profiles) > 1
                else "COUNTRY_SCENARIO_CONFIGURATION_" + status,
            ),
        )

    def classification(self, ident):
        return ClassificationResult.model_validate(self.classifier.get_result(ident))

    def country_evidence(self, ident, operation="execute"):
        with self.sessions() as session:
            run = self.get(session, g.RetrievalRunEntity, ident)
            self.authorize(run.project_id, operation)
        response = self.retrieval.scoped_saved_response(str(ident))
        if response["status"] != "COMPLETED" or not response["rag_context_pack"]:
            raise ValueError("completed scoped Phase1G retrieval required")
        return response

    def prepare(self, request: ApplicabilityRequest, operation="execute"):
        self.authorize(request.project_id, operation)
        snapshot, pin, scenarios, facts, _ = self.formal(
            request.project_id, request.analysis_snapshot_id, request.jurisdiction_id, operation
        )
        response = self.country_evidence(request.retrieval_run_id, operation)
        rag = RAGContextPack.model_validate(response["rag_context_pack"])
        q = response["query"]
        expected = (str(request.project_id), str(request.analysis_snapshot_id))
        if (q["project_id"], q["analysis_snapshot_id"]) != expected:
            raise LookupError("evidence belongs to another project/snapshot")
        retrieval_subject = (q["subject_type"], q.get("subject_id") or q["project_id"])
        if request.subject_type == "SCENARIO":
            if (
                request.subject_id not in scenarios
                or retrieval_subject != ("PROJECT", str(request.project_id))
                or not facts
            ):
                raise LookupError(
                    "scenario requires independent formal context/facts and project evidence"
                )
        elif retrieval_subject != (request.subject_type, str(request.subject_id)):
            raise LookupError("evidence belongs to another subject")
        profile = self.resolve_profile(
            request.project_id, request.analysis_snapshot_id, request.jurisdiction_id, operation
        )
        with self.sessions() as s:
            pins = self.pins(s, request.analysis_snapshot_id)
            cfgpins = [
                p
                for p in pins
                if p.pin_type == "PHASE1I_APPLICABILITY_CONFIG"
                and p.object_id == str(request.applicability_config_id)
            ]
            if len(cfgpins) != 1:
                raise LookupError("applicability config is not snapshot pinned")
            cfgrow, config = self.published(
                s, cfgpins[0], "APPLICABILITY_CONFIG", snapshot.analysis_as_of_date
            )
            if config.jurisdiction_id != request.jurisdiction_id:
                raise LookupError("applicability configuration jurisdiction mismatch")
            if profile.profiles and not all(
                request.applicability_config_id in p.config.applicability_config_ids
                for p in profile.profiles
            ):
                raise LookupError("applicability not in country profile")
            if not any(
                p.pin_type == "PHASE1I_KNOWLEDGE"
                and p.version_id == str(config.knowledge_version_id)
                for p in pins
            ):
                raise ValueError("canonical regulation version is not pinned")
            # Revalidated Phase1G universe is an upper bound, never broadened by profiles.
            if str(config.knowledge_version_id) not in rag.scope.filter_spec.version_filter:
                raise LookupError("regulation source no longer authorized")
            if request.subject_type == "DATA_ITEM":
                item = self.get(s, b.DataItemEntity, request.subject_id)
                detail = exact_item_detail(s, self.tenant, request.subject_id, pin.data_inventory_version)
                if (
                    item.project_id != str(request.project_id)
                    or detail.version != pin.data_inventory_version
                    or detail.validation_status != "VALIDATED"
                    or detail.review_required
                ):
                    raise LookupError("formal data item unavailable")
                items = (request.subject_id,)
                flows = ()
            elif request.subject_type == "DATA_FLOW":
                flow = self.get(s, b.DataFlowEdgeEntity, request.subject_id)
                detail = self.get(s, c.DataFlowEdgeDetailEntity, request.subject_id)
                if (
                    flow.project_id != str(request.project_id)
                    or detail.version != pin.data_flow_version
                    or detail.validation_status != "VALIDATED"
                ):
                    raise LookupError("formal data flow unavailable")
                items = tuple(UUID(v) for v in flow_item_ids(s, self.tenant, request.subject_id, pin.data_inventory_version))
                for ident in items:
                    linked_item = self.get(s, b.DataItemEntity, ident)
                    linked_detail = exact_item_detail(s, self.tenant, ident, pin.data_inventory_version)
                    if (
                        linked_item.project_id != str(request.project_id)
                        or linked_detail.version != pin.data_inventory_version
                        or linked_detail.validation_status != "VALIDATED"
                        or linked_detail.review_required
                    ):
                        raise LookupError("flow includes unavailable formal item")
                flows = (request.subject_id,)
            elif request.subject_type == "SCENARIO":
                items = ()
                flows = ()
            else:
                raise ValueError("unsupported applicability subject")
            versions = {
                p.version_id
                for p in s.scalars(
                    select(m.AnalysisSnapshotRegistryPinEntity).where(
                        m.AnalysisSnapshotRegistryPinEntity.tenant_id == self.tenant,
                        m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id
                        == str(request.analysis_snapshot_id),
                        m.AnalysisSnapshotRegistryPinEntity.pin_type == "RULE_V1",
                    )
                )
            }
            hitrows = [self.get(s, b.RuleHitEntity, ident) for ident in request.rule_hit_ids]
            hits = []
            for row in hitrows:
                if not row.formal_provenance_json or row.rule_version_ref not in versions:
                    raise LookupError("RuleHit is not published snapshot pinned")
                hit = RuleHit.model_validate(row.formal_provenance_json)
                version = self.get(s, m.RuleVersionEntity, row.rule_version_ref)
                if (str(hit.rule_version_id), str(hit.rule_id)) != (
                    row.rule_version_ref,
                    version.rule_definition_id,
                ):
                    raise LookupError("RuleHit canonical identity mismatch")
                if request.subject_type == "SCENARIO" and (row.subject_type, row.subject_id) != (
                    "SCENARIO",
                    str(request.subject_id),
                ):
                    raise LookupError("RuleHit belongs to another scenario")
                if request.subject_type != "SCENARIO" and (
                    row.subject_type != "DATA_ITEM" or row.subject_id not in {str(v) for v in items}
                ):
                    raise LookupError("RuleHit belongs to another data subject")
                if (
                    str(request.jurisdiction_id)
                    not in version.runtime_contract_json["scope"]["jurisdiction_ids"]
                ):
                    raise LookupError("RuleHit jurisdiction mismatch")
                if hit.jurisdiction_id is not None and hit.jurisdiction_id != request.jurisdiction_id:
                    raise LookupError("RuleHit execution jurisdiction mismatch")
                if hit.jurisdiction_id is None and version.runtime_contract_json["scope"]["jurisdiction_ids"] != [str(request.jurisdiction_id)]:
                    raise LookupError("legacy RuleHit jurisdiction is ambiguous")
                hits.append(hit)
            if len(profile.profiles) == 1:
                country = profile.profiles[0].config
                legal_version = self.get(
                    s, k.KnowledgeDocumentVersionEntity, config.knowledge_version_id
                )
                collection_version = self.get(
                    s, m.KnowledgeCollectionVersionEntity, legal_version.collection_version_id
                )
                if (
                    country.knowledge_collection_ids
                    and UUID(collection_version.knowledge_collection_id)
                    not in country.knowledge_collection_ids
                ):
                    raise LookupError("regulation outside country knowledge collections")
                packs = [
                    p
                    for p in pins
                    if p.pin_type == "PHASE1I_RULE_PACK"
                    and UUID(p.object_id) in country.rule_pack_ids
                ]
                if country.rule_pack_ids:
                    if {UUID(p.object_id) for p in packs} != set(country.rule_pack_ids):
                        raise LookupError("country rule pack not effectively pinned")
                    rules = {
                        ident
                        for p in packs
                        for ident in self.published(
                            s, p, "RULE_PACK", snapshot.analysis_as_of_date
                        )[1].rule_definition_ids
                    }
                    if not set(config.required_rule_ids) <= rules:
                        raise LookupError("applicability rules outside country packs")
            legal = self.legal_reference(s, config, rag, snapshot.analysis_as_of_date)
            # Scope bindings are narrowing constraints; no resolver refresh/search occurs.
            self.validate_adjustment(
                s, profile.scenario_configuration, rag, versions, snapshot.analysis_as_of_date, pins
            )
        classifications = tuple(
            self.classification(ident) for ident in request.classification_result_ids
        )
        citation_ids = {item.citation_id for item in rag.evidence_pack.items}
        with self.sessions() as s:
            evidence = tuple(
                UUID(v)
                for v in s.scalars(
                    select(b.EvidenceReferenceEntity.evidence_id)
                    .join(
                        b.CitationEntity,
                        b.CitationEntity.evidence_id == b.EvidenceReferenceEntity.evidence_id,
                    )
                    .where(
                        b.EvidenceReferenceEntity.tenant_id == self.tenant,
                        b.CitationEntity.tenant_id == self.tenant,
                        b.CitationEntity.citation_id.in_(citation_ids),
                        b.EvidenceReferenceEntity.status == "ACTIVE",
                        b.EvidenceReferenceEntity.validation_status.in_(["VALID", "VALIDATED"]),
                    )
                )
            )
        merged = profile.scenario_configuration
        if profile.status != "READY" and merged.status == "READY":
            merged = merged.model_copy(
                update={
                    "status": "REVIEW_REQUIRED",
                    "conflict_codes": profile.reason_codes
                    if profile.status == "CONFLICTED"
                    else (),
                }
            )
        return ApplicabilityInput(
            tenant_id=self.context.tenant_id,
            project_id=request.project_id,
            analysis_snapshot_id=request.analysis_snapshot_id,
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            data_item_ids=items,
            data_flow_ids=flows,
            scenario_definition_ids=scenarios,
            jurisdiction_id=request.jurisdiction_id,
            analysis_as_of_date=snapshot.analysis_as_of_date,
            context_version=pin.context_resolution_version,
            fact_refs=tuple(UUID(f.fact_id) for f in facts),
            country_profile=profile.profiles[0] if len(profile.profiles) == 1 else None,
            scenario_configuration=merged,
            applicability_config_id=request.applicability_config_id,
            applicability_config_version_id=UUID(cfgrow.version_id),
            applicability_config_version=cfgrow.version_no,
            config=config,
            canonical_legal_reference=legal,
            classifications=classifications,
            rule_hits=tuple(hits),
            evidence_ids=tuple(sorted(set(evidence), key=str)),
            evidence_pack_ids=(UUID(rag.evidence_pack.evidence_pack_id),),
            sufficiency=rag.knowledge_sufficiency,
            fallback_guidance_context=rag.fallback_guidance_context,
            review_required=rag.scope.review_required,
        )

    def legal_reference(self, s, config, rag, when):
        version = self.get(s, k.KnowledgeDocumentVersionEntity, config.knowledge_version_id)
        refs = []
        sources = []
        locators = []
        evidence = set()
        validity = "VALIDATED"
        if (
            not self.date_valid(version, when)
            or version.lifecycle not in {"ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"}
            or not version.approved_by
        ):
            validity = "SOURCE_NOT_EFFECTIVE"
        allowed = {
            i.citation_id
            for i in rag.evidence_pack.items
            if i.knowledge_version_id == str(config.knowledge_version_id)
            and i.jurisdiction_specific
            and i.jurisdiction_id == str(config.jurisdiction_id)
            and i.scope_validation_status == "VALIDATED"
            and i.source_tier in {"T1_PRIMARY_OFFICIAL", "T2_OFFICIAL_GUIDANCE"}
        }
        for ident in config.legal_basis_ids:
            basis = self.get(s, b.LegalBasisItemEntity, ident)
            if basis.jurisdiction_id != str(
                config.jurisdiction_id
            ) or basis.regulatory_structure_node_id not in {
                str(v) for v in config.regulatory_structure_node_ids
            }:
                raise LookupError("wrong legal basis jurisdiction/structure")
            node = self.get(s, b.RegulatoryStructureNodeEntity, basis.regulatory_structure_node_id)
            extension = s.scalar(
                select(k.KnowledgeStructureNodeEntity).where(
                    k.KnowledgeStructureNodeEntity.tenant_id == self.tenant,
                    k.KnowledgeStructureNodeEntity.regulatory_structure_node_id
                    == node.regulatory_structure_node_id,
                    k.KnowledgeStructureNodeEntity.knowledge_version_id
                    == str(config.knowledge_version_id),
                )
            )
            if (
                node.regulation_version_ref != str(config.knowledge_version_id)
                or node.jurisdiction_id != str(config.jurisdiction_id)
                or not self.date_valid(node, when)
                or not self.date_valid(basis, when)
            ):
                validity = "SOURCE_NOT_EFFECTIVE"
            if (
                extension is None
                or extension.citation_id not in allowed
                or basis.official_source != node.official_source
                or basis.citation_locator != extension.canonical_locator
                or not self.date_valid(basis, when)
            ):
                validity = "MISSING_LEGAL_BASIS"
                continue
            citation = self.get(s, b.CitationEntity, extension.citation_id)
            reference = self.get(s, b.EvidenceReferenceEntity, citation.evidence_id)
            if (
                reference.validation_status not in {"VALID", "VALIDATED"}
                or reference.status != "ACTIVE"
            ):
                validity = "MISSING_LEGAL_BASIS"
                continue
            refs.append(UUID(basis.legal_basis_id))
            sources.append(basis.official_source)
            locators.append(basis.citation_locator)
            evidence.add(UUID(citation.evidence_id))
        return CanonicalLegalReference(
            knowledge_document_id=UUID(version.document_id),
            knowledge_version_id=UUID(version.knowledge_version_id),
            jurisdiction_id=config.jurisdiction_id,
            regulatory_structure_node_ids=config.regulatory_structure_node_ids,
            legal_basis_ids=tuple(refs),
            evidence_ids=tuple(sorted(evidence, key=str)),
            official_sources=tuple(sources),
            citation_locators=tuple(locators),
            effective_from=version.effective_from,
            effective_to=version.effective_to,
            validation_status=validity,
        )

    def validate_adjustment(self, s, adjustment, rag, rule_versions, when, pins):
        for ident in (
            *adjustment.required_skill_ids,
            *adjustment.conditional_skill_ids,
            *adjustment.disabled_skill_ids,
        ):
            matches = [
                p for p in pins if p.pin_type == "PHASE1I_SKILL" and p.object_id == str(ident)
            ]
            if len(matches) != 1:
                raise LookupError("scenario skill registry version is not pinned")
            version = self.get(s, m.MetadataVersionEntity, matches[0].version_id)
            definition = self.get(s, m.MetadataDefinitionEntity, ident)
            if (
                definition.kind != "SKILL"
                or version.definition_id != str(ident)
                or version.version_no != matches[0].version_no
                or not self.date_valid(version, when)
                or version.lifecycle_status not in {"ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"}
            ):
                raise LookupError("invalid historical skill registry version")
        for kind, model, identifiers in (
            ("KNOWLEDGE_BINDING", m.KnowledgeBindingEntity, adjustment.knowledge_scope_bindings),
            ("RULE_BINDING", m.RuleBindingEntity, adjustment.rule_scope_bindings),
            ("TEMPLATE_BINDING", m.TemplateBindingEntity, adjustment.template_scope_bindings),
        ):
            for ident in identifiers:
                binding = self.get(s, model, ident)
                payload = {
                    col.name: str(getattr(binding, col.name)) for col in model.__table__.columns
                }
                expected = str(ident) + ":" + hash_value(payload)
                if not any(
                    p.pin_type == "PHASE1I_" + kind
                    and p.object_id == str(ident)
                    and p.logical_key == expected
                    and p.version_no == binding.record_version
                    for p in pins
                ):
                    raise LookupError("scenario binding changed after snapshot pin")
        if adjustment.evidence_requirement_profile_id:
            model = g.POLICY_MODELS["sufficiency"]
            actual = s.scalar(
                select(model).where(
                    model.tenant_id == self.tenant,
                    model.policy_version_id == rag.knowledge_sufficiency.policy_version,
                )
            )
            if actual is None or actual.policy_id != str(
                adjustment.evidence_requirement_profile_id
            ):
                raise ValueError("scenario evidence requirement policy mismatch")
        for ident in adjustment.knowledge_scope_bindings:
            binding = self.get(s, m.KnowledgeBindingEntity, ident)
            if str(ident) not in rag.scope.filter_spec.binding_filter or not self.date_valid(
                binding, when
            ):
                raise LookupError("scenario knowledge binding outside authorized pinned scope")
        for ident in adjustment.rule_scope_bindings:
            binding = self.get(s, m.RuleBindingEntity, ident)
            if binding.rule_version_id not in rule_versions or not self.date_valid(binding, when):
                raise LookupError("scenario rule binding outside pinned scope")
        for ident in adjustment.template_scope_bindings:
            binding = self.get(s, m.TemplateBindingEntity, ident)
            self.validate_resource(
                s, m.TemplateVersionEntity, binding.template_version_id, when, historical=True
            )
            if not self.date_valid(binding, when):
                raise LookupError("scenario template binding ineffective")

    def save(self, request, result):
        self.authorize(request.project_id)
        if (
            result.tenant_id,
            result.project_id,
            result.analysis_snapshot_id,
            result.subject_type,
            result.subject_id,
            result.jurisdiction_id,
            result.applicability_config_id,
        ) != (
            self.context.tenant_id,
            request.project_id,
            request.analysis_snapshot_id,
            request.subject_type,
            request.subject_id,
            request.jurisdiction_id,
            request.applicability_config_id,
        ):
            raise LookupError("applicability result identity mismatch")
        request_json = request.model_dump(mode="json")
        fingerprint = hash_value(request_json)
        with self.sessions() as s, s.begin():
            self.snapshot(s, request.project_id, request.analysis_snapshot_id, True)
            row = s.scalar(
                select(i.RegulationApplicabilityResultEntity).where(
                    i.RegulationApplicabilityResultEntity.tenant_id == self.tenant,
                    i.RegulationApplicabilityResultEntity.project_id == str(request.project_id),
                    i.RegulationApplicabilityResultEntity.analysis_snapshot_id
                    == str(request.analysis_snapshot_id),
                    i.RegulationApplicabilityResultEntity.subject_type == request.subject_type,
                    i.RegulationApplicabilityResultEntity.subject_id == str(request.subject_id),
                    i.RegulationApplicabilityResultEntity.jurisdiction_id
                    == str(request.jurisdiction_id),
                    i.RegulationApplicabilityResultEntity.applicability_config_version_id
                    == str(result.applicability_config_version_id),
                    i.RegulationApplicabilityResultEntity.retrieval_run_id
                    == str(request.retrieval_run_id),
                )
            )
            if row:
                saved = RegulationApplicabilityResult.model_validate(row.result_json)
                if (
                    row.owner_actor_id != self.context.permission.actor_id
                    or row.input_fingerprint != fingerprint
                ):
                    raise ValueError("applicability retry input conflict")
                self.validate_saved(saved, result)
                return saved
            # Reuse canonical LegalBasis M:N links; never duplicate LegalBasis objects.
            for basis in result.legal_basis_ids:
                for hit in result.rule_hit_ids:
                    hit_row = self.get(s, b.RuleHitEntity, hit)
                    formal_hit = RuleHit.model_validate(hit_row.formal_provenance_json)
                    if basis not in formal_hit.legal_basis_ids:
                        continue
                    exists = s.scalar(
                        select(b.LegalBasisRuleHitLinkEntity).where(
                            b.LegalBasisRuleHitLinkEntity.tenant_id == self.tenant,
                            b.LegalBasisRuleHitLinkEntity.legal_basis_id == str(basis),
                            b.LegalBasisRuleHitLinkEntity.rule_hit_id == str(hit),
                        )
                    )
                    if not exists:
                        s.add(
                            b.LegalBasisRuleHitLinkEntity(
                                legal_basis_rule_hit_link_id=str(uuid4()),
                                tenant_id=self.tenant,
                                legal_basis_id=str(basis),
                                rule_hit_id=str(hit),
                            )
                        )
                basis_row = self.get(s, b.LegalBasisItemEntity, basis)
                extension = s.scalar(
                    select(k.KnowledgeStructureNodeEntity).where(
                        k.KnowledgeStructureNodeEntity.tenant_id == self.tenant,
                        k.KnowledgeStructureNodeEntity.regulatory_structure_node_id
                        == basis_row.regulatory_structure_node_id,
                        k.KnowledgeStructureNodeEntity.knowledge_version_id
                        == str(result.regulation_version_ref),
                    )
                )
                citation = (
                    self.get(s, b.CitationEntity, extension.citation_id) if extension else None
                )
                for evidence in result.evidence_ids:
                    if citation is None or str(evidence) != citation.evidence_id:
                        continue
                    exists = s.scalar(
                        select(b.LegalBasisEvidenceLinkEntity).where(
                            b.LegalBasisEvidenceLinkEntity.tenant_id == self.tenant,
                            b.LegalBasisEvidenceLinkEntity.legal_basis_id == str(basis),
                            b.LegalBasisEvidenceLinkEntity.evidence_id == str(evidence),
                        )
                    )
                    if not exists:
                        s.add(
                            b.LegalBasisEvidenceLinkEntity(
                                legal_basis_evidence_link_id=str(uuid4()),
                                tenant_id=self.tenant,
                                legal_basis_id=str(basis),
                                evidence_id=str(evidence),
                            )
                        )
            s.add(
                i.RegulationApplicabilityResultEntity(
                    applicability_result_id=str(result.applicability_result_id),
                    tenant_id=self.tenant,
                    project_id=str(request.project_id),
                    analysis_snapshot_id=str(request.analysis_snapshot_id),
                    jurisdiction_id=str(request.jurisdiction_id),
                    subject_type=request.subject_type,
                    subject_id=str(request.subject_id),
                    regulation_version_ref=str(result.regulation_version_ref),
                    applicability_config_version_id=str(result.applicability_config_version_id),
                    country_profile_version_id=str(result.country_profile_version_id)
                    if result.country_profile_version_id
                    else None,
                    retrieval_run_id=str(request.retrieval_run_id),
                    owner_actor_id=self.context.permission.actor_id,
                    applicability_status=result.applicability_status,
                    request_json=request_json,
                    input_fingerprint=fingerprint,
                    result_json=result.model_dump(mode="json"),
                )
            )
        return result

    @staticmethod
    def validate_saved(saved, current):
        if not set(saved.evidence_ids) <= set(current.evidence_ids):
            raise LookupError("applicability evidence no longer authorized")
        if (
            saved.applicability_status
            in {"APPLICABLE", "NOT_APPLICABLE", "CONDITIONALLY_APPLICABLE"}
            and current.applicability_status != saved.applicability_status
        ):
            raise LookupError("saved applicability requires current evidence revalidation")

    def read(self, ident):
        from crossborder_compliance.domain.regulation_applicability import (
            RegulationApplicabilitySkill,
        )

        with self.sessions() as s:
            row = self.get(s, i.RegulationApplicabilityResultEntity, ident)
            self.authorize(row.project_id, "read")
            if row.owner_actor_id != self.context.permission.actor_id:
                raise LookupError("applicability resource not found")
            request = ApplicabilityRequest.model_validate(row.request_json)
            saved = RegulationApplicabilityResult.model_validate(row.result_json)
        current = RegulationApplicabilitySkill().execute(self.prepare(request, operation="read"))
        self.validate_saved(saved, current)
        return saved

    def scenario_rule_hits(
        self, project_id, snapshot_id, scenario_id, jurisdiction_id, retrieval_run_id
    ):
        """Explicit Phase1H engine delegation on formal scenario facts; never classification."""
        from crossborder_compliance.domain.rule_ast import typed_value
        from crossborder_compliance.domain.rules import RuleFactContext, SafeRuleEngine
        from crossborder_compliance.infrastructure.persistence.rule_governance import as_rule

        snapshot, pin, scenarios, facts, _ = self.formal(project_id, snapshot_id, jurisdiction_id)
        if scenario_id not in scenarios or not facts:
            raise LookupError("validated scenario and business facts required")
        response = self.country_evidence(retrieval_run_id)
        query = response["query"]
        if (
            query["project_id"],
            query["analysis_snapshot_id"],
            query["subject_type"],
            query.get("subject_id") or query["project_id"],
        ) != (str(project_id), str(snapshot_id), "PROJECT", str(project_id)):
            raise LookupError("scenario requires same-snapshot project evidence")
        rag = RAGContextPack.model_validate(response["rag_context_pack"])
        with self.sessions() as s, s.begin():
            self.snapshot(s, project_id, snapshot_id, True)
            pins = s.scalars(
                select(m.AnalysisSnapshotRegistryPinEntity).where(
                    m.AnalysisSnapshotRegistryPinEntity.tenant_id == self.tenant,
                    m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == str(snapshot_id),
                    m.AnalysisSnapshotRegistryPinEntity.pin_type == "RULE_V1",
                )
            ).all()
            rules = tuple(as_rule(self.get(s, m.RuleVersionEntity, p.version_id)) for p in pins)
            if not rules:
                raise ValueError("explicit Phase1H rule pins required")
            schemas = {}
            for rule in rules:
                for key, schema in rule.contract.fields.items():
                    if key in schemas and schemas[key] != schema:
                        raise ValueError("ambiguous pinned fact schema")
                    schemas[key] = schema
            values = {}
            refs = {}
            for fact in facts:
                key = fact.fact_type.lower()
                if key not in schemas:
                    continue
                if key in values:
                    raise ValueError("ambiguous formal business fact")
                values[key] = typed_value(fact.normalized_value_json, schemas[key], literal=True)
                refs[key] = (UUID(fact.fact_id),)
            citation_ids = [e.citation_id for e in rag.evidence_pack.items]
            evidence = s.scalars(
                select(b.EvidenceReferenceEntity)
                .join(
                    b.CitationEntity,
                    b.CitationEntity.evidence_id == b.EvidenceReferenceEntity.evidence_id,
                )
                .where(
                    b.EvidenceReferenceEntity.tenant_id == self.tenant,
                    b.CitationEntity.tenant_id == self.tenant,
                    b.CitationEntity.citation_id.in_(citation_ids),
                    b.EvidenceReferenceEntity.validation_status.in_(["VALID", "VALIDATED"]),
                    b.EvidenceReferenceEntity.status == "ACTIVE",
                )
            ).all()
            scenario_codes = tuple(
                s.scalars(
                    select(m.MetadataDefinitionEntity.code).where(
                        m.MetadataDefinitionEntity.tenant_id == self.tenant,
                        m.MetadataDefinitionEntity.definition_id.in_([str(v) for v in scenarios]),
                    )
                )
            )
            products = tuple(
                s.scalars(
                    select(m.MetadataDefinitionEntity.code).where(
                        m.MetadataDefinitionEntity.tenant_id == self.tenant,
                        m.MetadataDefinitionEntity.definition_id.in_(
                            rag.structured_context.dimensions.get("product", ())
                        ),
                    )
                )
            )
            context = RuleFactContext(
                tenant_id=self.context.tenant_id,
                project_id=project_id,
                analysis_snapshot_id=snapshot_id,
                context_version=pin.context_resolution_version,
                data_item_id=None,
                jurisdiction_id=jurisdiction_id,
                as_of=snapshot.analysis_as_of_date,
                values=values,
                fact_refs=refs,
                evidence_ids=tuple(UUID(e.evidence_id) for e in evidence),
                evidence_types=tuple(sorted({e.evidence_type for e in evidence})),
                evidence_pack_ids=(UUID(rag.evidence_pack.evidence_pack_id),),
                scenario_codes=scenario_codes,
                product_codes=products,
                confidence=min(f.confidence for f in facts),
                review_required=rag.scope.review_required,
            )
            hits = SafeRuleEngine().evaluate(
                rules,
                context,
                pinned_versions=frozenset(UUID(p.version_id) for p in pins),
                historical=True,
            )
            result = []
            for hit in hits:
                prior = s.scalars(
                    select(b.RuleHitEntity).where(
                        b.RuleHitEntity.tenant_id == self.tenant,
                        b.RuleHitEntity.subject_type == "SCENARIO",
                        b.RuleHitEntity.subject_id == str(scenario_id),
                        b.RuleHitEntity.rule_version_ref == str(hit.rule_version_id),
                    )
                ).all()
                saved = [
                    r
                    for r in prior
                    if r.formal_provenance_json
                    and r.formal_provenance_json["analysis_snapshot_id"] == str(snapshot_id)
                    and (r.formal_provenance_json.get("jurisdiction_id") == str(jurisdiction_id)
                         or (r.formal_provenance_json.get("jurisdiction_id") is None
                             and [str(jurisdiction_id)] == [str(j) for r in rules if r.rule_version_id == hit.rule_version_id for j in r.contract.scope.jurisdiction_ids]))
                ]
                if saved:
                    historical = RuleHit.model_validate(saved[0].formal_provenance_json)
                    if not set(historical.evidence_ids) <= set(context.evidence_ids):
                        raise LookupError("scenario evidence revoked")
                    result.append(historical)
                else:
                    s.add(
                        b.RuleHitEntity(
                            rule_hit_id=str(hit.rule_hit_id),
                            tenant_id=self.tenant,
                            rule_version_ref=str(hit.rule_version_id),
                            subject_type="SCENARIO",
                            subject_id=str(scenario_id),
                            evidence_json={"ids": [str(v) for v in hit.evidence_ids]},
                            formal_provenance_json=hit.model_dump(mode="json"),
                        )
                    )
                    result.append(hit)
            return tuple(result)

from uuid import UUID, uuid4

from sqlalchemy import func, select

from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence.config_admin_repositories import (
    PostgresGovernedArtifactAdminRepository,
)
from crossborder_compliance.infrastructure.persistence.rule_governance import (
    contract_values,
    replace_tests,
    validate_version,
)


class PostgresRuleAdminRepository(PostgresGovernedArtifactAdminRepository):
    def __init__(self, sessions, context):
        super().__init__(sessions, context, "rules")

    def create_version(self, definition_id: UUID, payload: dict):
        self._require(self._policy.draft_scope)
        values = contract_values(payload)
        if not values:
            raise ValueError("new rule versions require runtime_contract")
        with self._sessions() as s, s.begin():
            definition = s.scalar(select(m.RuleDefinitionEntity).where(
                m.RuleDefinitionEntity.rule_definition_id == str(definition_id),
                m.RuleDefinitionEntity.tenant_id == self.tenant_id).with_for_update())
            if definition is None:
                raise LookupError("rule definition not found")
            number = (s.scalar(select(func.max(m.RuleVersionEntity.version_no)).where(
                m.RuleVersionEntity.tenant_id == self.tenant_id,
                m.RuleVersionEntity.rule_definition_id == str(definition_id))) or 0) + 1
            row = m.RuleVersionEntity(rule_version_id=str(uuid4()), rule_definition_id=str(definition_id),
                tenant_id=self.tenant_id, version_no=number, lifecycle_status="DRAFT", **values)
            s.add(row)
            s.flush()
            replace_tests(s, row, payload)
            return self._row_dict(row)

    def validate(self, version_id: UUID):
        self._require(self._policy.draft_scope)
        with self._sessions() as s:
            row = s.scalar(select(m.RuleVersionEntity).where(
                m.RuleVersionEntity.rule_version_id == str(version_id),
                m.RuleVersionEntity.tenant_id == self.tenant_id))
            if row is None:
                raise LookupError("rule version not found")
            return validate_version(s, row)

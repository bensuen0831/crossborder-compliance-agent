"""Northbound adaptation only: all business capabilities are existing use cases."""
from crossborder_compliance.application.integrations import IntegrationFailure
from crossborder_compliance.application.intake_services import CreateProjectFromIntake, UpdateIntakeDraft
from crossborder_compliance.domain.integrations import IntegrationScope


class ExternalChannelService:
    def __init__(self, integration, principal, canonical):
        self.integration, self.principal, self.canonical = integration, principal, canonical

    def _context(self, scope, project=None):
        return self.integration.authorize(self.principal, scope, project)

    def _model_preference(self, facts):
        if facts.ai_model_preference is not None:
            self._context(IntegrationScope.MODEL_SELECT)

    def create(self, body, key):
        self._model_preference(body.facts)
        ctx = self._context(IntegrationScope.PROJECT_CREATE)
        view = self.canonical.intake(ctx).create(CreateProjectFromIntake(
            name=body.name, facts=body.facts, idempotency_key=key))
        self.integration.repository.bind_created(self.principal, view.project_id)
        return view

    def read_intake(self, project, version=None):
        return self.canonical.intake(self._context(IntegrationScope.PROJECT_READ, project)).read(project, version)

    def update(self, project, body, key):
        self._model_preference(body.facts)
        return self.canonical.intake(self._context(IntegrationScope.INTAKE_WRITE, project)).update(
            project, UpdateIntakeDraft(expected_version=body.expected_version, facts=body.facts, idempotency_key=key))

    def confirm(self, project, body, key):
        ctx = self._context(IntegrationScope.INTAKE_WRITE, project)
        return self.canonical.idempotent(self.principal, f"confirm:{project}", key,
            body.model_dump(mode="json"),
            lambda: self.canonical.intake(ctx).confirm(project, body),
            lambda ref: self.canonical.intake(ctx).read(project, int(ref)),
            lambda result: str(result.version))

    def successor(self, project, command):
        self._context(IntegrationScope.INTAKE_WRITE, project)
        context = self._context(IntegrationScope.DOCUMENT_UPLOAD, project)
        return self.canonical.documents(context).supersede(project, command)

    def documents(self, project):
        return self.canonical.documents(self._context(IntegrationScope.PROJECT_READ, project)).list_inputs(project)

    def upload(self, project, command, filename, media_type, content):
        return self.canonical.documents(self._context(IntegrationScope.DOCUMENT_UPLOAD, project)).upload(
            project, command, filename=filename, media_type=media_type, content=content)

    def document_action(self, project, version_id, command, action):
        service = self.canonical.documents(self._context(IntegrationScope.DOCUMENT_UPLOAD, project))
        if action not in {"parse", "unlink"}:
            raise IntegrationFailure("INVALID_INPUT",422)
        return getattr(service, action)(project, version_id, command)

    def eligible_models(self, project):
        return self.canonical.eligible_models(self._context(IntegrationScope.MODEL_SELECT,project),project)

    def start(self, project, snapshot, key):
        ctx = self._context(IntegrationScope.COMPLIANCE_ANALYZE,project)
        return self.canonical.enqueue(self.principal,ctx,project,snapshot,key)

    def status(self, run):
        project,snapshot=self.canonical.run_scope(self.principal.tenant_id,run)
        ctx=self._context(IntegrationScope.COMPLIANCE_READ,project)
        return self.canonical.status(ctx,run,project,snapshot)

    def result(self, run):
        project,_=self.canonical.run_scope(self.principal.tenant_id,run)
        ctx=self._context(IntegrationScope.COMPLIANCE_READ,project)
        return self.canonical.result(ctx,run)

    def events(self,run,after=None):
        project,snapshot=self.canonical.run_scope(self.principal.tenant_id,run)
        self._context(IntegrationScope.COMPLIANCE_READ,project)
        return self.canonical.events(self.principal.tenant_id,project,snapshot,run,after)

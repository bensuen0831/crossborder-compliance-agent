"""Empirical crash after canonical durable task acceptance, before binary read."""
import json,os,sys
from pathlib import Path
from uuid import UUID
from types import SimpleNamespace
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.document_input_composition import document_input_service
from crossborder_compliance.application.document_upload import DraftDocumentRequest

values=json.loads(Path(sys.argv[1]).read_text())
_,sf=build_session_factory(get_settings().database_url)
context=RepositoryContext.user(UUID(values['tenant']),values['actor'],set(values['scopes']))
class CrashStorage:
    def get(self,ref): os._exit(75)
request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(document_object_storage=CrashStorage())))
service=document_input_service(request,sf,context)
service.parse(UUID(values['project']),UUID(values['document_version']),DraftDocumentRequest(expected_version=values['version'],idempotency_key=values['key']))
raise SystemExit('crash boundary not reached')

"""Request-scoped authorized composition; provider ports stay infrastructure."""
import os

from crossborder_compliance.application.document_upload import DocumentCapabilityError, DocumentFilePolicy, ProjectDocumentService
from crossborder_compliance.infrastructure.document_storage import FileObjectStorageAdapter
from crossborder_compliance.infrastructure.persistence.document_repositories import PostgresDocumentIntelligenceRepository


def document_input_service(request, sessions, context):
    raw=getattr(request.app.state,"document_file_policy",None) or os.environ.get("DOCUMENT_FILE_POLICY_JSON")
    if raw is None: raise DocumentCapabilityError("CAPABILITY_NOT_CONFIGURED: document file policy")
    policy=raw if isinstance(raw,DocumentFilePolicy) else DocumentFilePolicy.model_validate_json(raw) if isinstance(raw,str) else DocumentFilePolicy.model_validate(raw)
    storage=getattr(request.app.state,"document_object_storage",None)
    if storage is None:
        root=os.environ.get("DOCUMENT_OBJECT_STORAGE_ROOT")
        if not root: raise DocumentCapabilityError("CAPABILITY_NOT_CONFIGURED: object storage")
        storage=FileObjectStorageAdapter(root)
    repo=PostgresDocumentIntelligenceRepository(sessions,context)
    repo.file_policy=policy; repo.storage=storage
    repo.scanner=getattr(request.app.state,"document_malware_scanner",None)
    return ProjectDocumentService(repo)

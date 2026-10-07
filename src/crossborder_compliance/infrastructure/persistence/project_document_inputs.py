"""Canonical document repository operations; exact intake-version relationships."""
import hashlib
from contextlib import contextmanager
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from crossborder_compliance.application.document_upload import (
    DocumentCapabilityError, DocumentInputsView, DocumentInputView,
)
from crossborder_compliance.application.document_services import DocumentIngestionService, DocumentParseService
from crossborder_compliance.application.intake_services import IntakeFacts
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence import document_models as d
from crossborder_compliance.infrastructure.persistence.project_intake import IntakeConflict


@contextmanager
def joined_sessions(connection):
    with Session(bind=connection,join_transaction_mode="create_savepoint",expire_on_commit=False) as child:
        yield child


def links(session, tenant, version_id):
    return list(session.scalars(select(d.ProjectVersionDocumentLinkEntity.document_version_id).where(
        d.ProjectVersionDocumentLinkEntity.tenant_id==tenant,
        d.ProjectVersionDocumentLinkEntity.project_version_id==str(version_id))))


def copy_links(session, tenant, old, new):
    wanted=set(new.intake_json.get("uploaded_documents", []))
    for version_id in links(session, tenant, old.project_version_id):
        version=session.get(b.DocumentVersionEntity,version_id)
        if version.document_id in wanted:
            session.add(d.ProjectVersionDocumentLinkEntity(link_id=str(uuid4()),tenant_id=tenant,
                project_version_id=new.project_version_id,document_version_id=version_id))


class ProjectDocumentOperations:
    """Mixin of PostgresDocumentIntelligenceRepository, never a parallel store."""
    def _input_project(self, session, project_id, operation, lock=False):
        from crossborder_compliance.infrastructure.persistence.postgres_repositories import PostgresProjectRepository
        owner=PostgresProjectRepository(self._sessions,self._context)
        owner._intake_permission("read" if operation=="read" else "update")
        if not self._context.permission.system and f"document:{operation}" not in self._context.permission.scopes:
            raise PermissionError("document input not found")
        project=owner._intake_project(session,project_id,lock)
        return owner,project,owner._intake_current(session,project)

    def _input_view(self, session, project_id, row):
        result=[]
        for version_id in links(session,self.tenant_id,row.project_version_id):
            version=session.get(b.DocumentVersionEntity,version_id)
            detail=session.get(d.DocumentVersionIntelligenceEntity,version_id)
            doc=session.get(b.DocumentEntity,version.document_id)
            if doc.project_id!=str(project_id) or version.tenant_id!=self.tenant_id or detail.tenant_id!=self.tenant_id:
                raise LookupError("document input not found")
            pin=None
            if row.status!="DRAFT":
                snapshot=session.scalar(select(b.AnalysisSnapshotEntity).where(b.AnalysisSnapshotEntity.tenant_id==self.tenant_id,b.AnalysisSnapshotEntity.project_version_id==row.project_version_id))
                if snapshot:
                    pin=session.scalar(select(d.AnalysisSnapshotParseRunPinEntity.parse_run_id).where(d.AnalysisSnapshotParseRunPinEntity.tenant_id==self.tenant_id,d.AnalysisSnapshotParseRunPinEntity.analysis_snapshot_id==snapshot.analysis_snapshot_id,d.AnalysisSnapshotParseRunPinEntity.document_version_id==version_id))
            query=select(d.DocumentParseRunDetailEntity).where(d.DocumentParseRunDetailEntity.tenant_id==self.tenant_id,d.DocumentParseRunDetailEntity.document_version_id==version_id)
            if pin: query=query.where(d.DocumentParseRunDetailEntity.parse_run_id==pin)
            run=session.scalar(query.order_by(d.DocumentParseRunDetailEntity.parse_run_version.desc()))
            task=session.scalar(select(d.DocumentParseTaskEntity).where(d.DocumentParseTaskEntity.tenant_id==self.tenant_id,d.DocumentParseTaskEntity.document_version_id==version_id).order_by(d.DocumentParseTaskEntity.updated_at.desc()))
            quality=session.scalar(select(d.DocumentParseQualityEntity).where(d.DocumentParseQualityEntity.tenant_id==self.tenant_id,d.DocumentParseQualityEntity.parse_run_id==run.parse_run_id)) if run else None
            result.append(DocumentInputView(document_id=doc.document_id,document_version_id=version_id,document_version=version.version_no,
                filename=detail.filename,size_bytes=detail.size_bytes,media_type=version.mime_type,content_hash=version.content_hash,
                parse_status=session.get(b.DocumentParseRunEntity,run.parse_run_id).status if run else task.status if task else "STORED",quality_status=quality.quality_status if quality else None,
                parse_run_id=run.parse_run_id if run else None,error_code=run.error_code if run else task.error_code if task else None,
                counts={"pages":run.page_count,"tables":run.table_count,"images":run.image_count} if run else {}))
        return DocumentInputsView(project_id=project_id,project_version_id=row.project_version_id,intake_version=row.version_no,intake_status=row.status,items=result)

    def list_inputs(self, project_id, version=None):
        with self._sessions() as s:
            _,_,row=self._input_project(s,project_id,"read")
            if version is not None:
                row=s.scalar(select(b.ProjectVersionEntity).where(b.ProjectVersionEntity.tenant_id==self.tenant_id,b.ProjectVersionEntity.project_id==str(project_id),b.ProjectVersionEntity.version_no==version))
                if row is None: raise LookupError("intake version not found")
            return self._input_view(s,project_id,row)

    def _append_inputs(self, session, owner, project, old, version_ids):
        from crossborder_compliance.application.intake_services import UpdateIntakeDraft
        values={k:v for k,v in old.intake_json.items() if k in IntakeFacts.model_fields}
        values["uploaded_documents"]=list(dict.fromkeys(session.get(b.DocumentVersionEntity,v).document_id for v in version_ids))
        row=b.ProjectVersionEntity(project_version_id=str(uuid4()),tenant_id=self.tenant_id,project_id=project.project_id,
            version_no=old.version_no+1,status="DRAFT",intake_json=owner._intake_payload(IntakeFacts.model_validate(values),project,old.version_no+1))
        old.status="SUPERSEDED"; session.add(row); session.flush()
        project.active_version_id=row.project_version_id; project.record_version+=1
        for version_id in version_ids:
            session.add(d.ProjectVersionDocumentLinkEntity(link_id=str(uuid4()),tenant_id=self.tenant_id,project_version_id=row.project_version_id,document_version_id=version_id))
        session.flush()
        return row

    def _draft(self, row, expected):
        if row.version_no!=expected: raise IntakeConflict("STALE_INTAKE_VERSION")
        if row.status!="DRAFT": raise IntakeConflict("CONFIRMED_INTAKE_IMMUTABLE")

    def upload(self, project_id, request, *, filename, media_type, content, replace_document_id=None):
        from crossborder_compliance.infrastructure.persistence.document_repositories import PostgresDocumentIntelligenceRepository
        with self._sessions() as s,s.begin():
            owner,project,row=self._input_project(s,project_id,"upload",True)
            digest=hashlib.sha256(content).hexdigest()
            key,duplicate=owner._intake_key(s,f"document-upload:{project_id}",request.idempotency_key,
                dict(expected_version=request.expected_version,filename=filename,media_type=media_type,hash=digest,replace=str(replace_document_id)))
            if duplicate:
                historical=s.get(b.ProjectVersionEntity,key.response_ref)
                return self._input_view(s,project_id,historical)
            self._draft(row,request.expected_version)
            if self.file_policy is None or self.storage is None:
                raise DocumentCapabilityError("CAPABILITY_NOT_CONFIGURED: document upload")
            safe,media=self.file_policy.validate_content(filename,media_type,content)
            if self.file_policy.scan_required and self.scanner is None:
                raise DocumentCapabilityError("CAPABILITY_NOT_CONFIGURED: malware scanner required")
            current=links(s,self.tenant_id,row.project_version_id)
            existing=s.scalar(select(b.DocumentVersionEntity).where(b.DocumentVersionEntity.tenant_id==self.tenant_id,b.DocumentVersionEntity.content_hash==digest))
            if existing:
                doc=s.get(b.DocumentEntity,existing.document_id)
                if doc.project_id!=str(project_id) or replace_document_id and str(replace_document_id)!=doc.document_id:
                    raise IntakeConflict("DOCUMENT_CONTENT_ALREADY_BOUND")
                version_id=existing.document_version_id
            else:
                child=lambda: joined_sessions(s.connection())
                documents=PostgresDocumentIntelligenceRepository(child,self._context)
                ingestion=DocumentIngestionService(documents,self.storage,self.scanner,max_size_bytes=self.file_policy.max_size_bytes,scan_required=self.file_policy.scan_required)
                if replace_document_id:
                    previous=s.get(b.DocumentEntity,str(replace_document_id))
                    if previous is None or previous.tenant_id!=self.tenant_id or previous.project_id!=str(project_id) or not any(s.get(b.DocumentVersionEntity,v).document_id==previous.document_id for v in current):
                        raise LookupError("replacement document not attached")
                    result=ingestion.add_version(tenant_id=self._context.tenant_id,document_id=replace_document_id,filename=safe,mime_type=media,content=content)
                else:
                    named = s.scalar(select(b.DocumentEntity).where(b.DocumentEntity.tenant_id == self.tenant_id,
                        b.DocumentEntity.project_id == str(project_id), b.DocumentEntity.name == safe))
                    if named is not None:
                        result=ingestion.add_version(tenant_id=self._context.tenant_id,document_id=UUID(named.document_id),filename=safe,mime_type=media,content=content)
                    else:
                        result=ingestion.ingest(tenant_id=self._context.tenant_id,project_id=project_id,filename=safe,mime_type=media,content=content)
                version_id=str(result["document_version_id"])
                audit=s.get(d.DocumentVersionIntelligenceEntity,version_id)
                audit.upload_provenance_json=dict(actor_ref=self._context.permission.actor_id,origin="DOCUMENT_UPLOAD",policy_version=self.file_policy.version,policy_digest=self.file_policy.digest,
                    scan_status="PASS" if self.scanner is not None else "NOT_REQUESTED",original_filename=filename,content_hash=digest)
            doc_id=s.get(b.DocumentVersionEntity,version_id).document_id
            current=[v for v in current if s.get(b.DocumentVersionEntity,v).document_id!=doc_id]+[version_id]
            new=self._append_inputs(s,owner,project,row,current); key.response_ref=new.project_version_id
            return self._input_view(s,project_id,new)

    def unlink(self, project_id, version_id, request):
        with self._sessions() as s,s.begin():
            owner,project,row=self._input_project(s,project_id,"unlink",True)
            key,duplicate=owner._intake_key(s,f"document-unlink:{project_id}",request.idempotency_key,request.model_dump(mode="json")|{"document_version_id":str(version_id)})
            if duplicate: return self._input_view(s,project_id,s.get(b.ProjectVersionEntity,key.response_ref))
            self._draft(row,request.expected_version)
            current=links(s,self.tenant_id,row.project_version_id)
            if str(version_id) not in current: raise LookupError("document input not attached")
            new=self._append_inputs(s,owner,project,row,[v for v in current if v!=str(version_id)]); key.response_ref=new.project_version_id
            return self._input_view(s,project_id,new)

    def supersede(self, project_id, request):
        with self._sessions() as s,s.begin():
            owner,project,row=self._input_project(s,project_id,"upload",True)
            key,duplicate=owner._intake_key(s,f"document-supersede:{project_id}",request.idempotency_key,request.model_dump(mode="json"))
            if duplicate: return self._input_view(s,project_id,s.get(b.ProjectVersionEntity,key.response_ref))
            if row.version_no!=request.expected_version: raise IntakeConflict("STALE_INTAKE_VERSION")
            if row.status!="CONFIRMED": raise IntakeConflict("CONFIRMED_INTAKE_REQUIRED")
            new=self._append_inputs(s,owner,project,row,links(s,self.tenant_id,row.project_version_id)); key.response_ref=new.project_version_id
            return self._input_view(s,project_id,new)

    def parse(self, project_id, version_id, request):
        from crossborder_compliance.infrastructure.persistence.document_repositories import PostgresDocumentIntelligenceRepository
        from crossborder_compliance.infrastructure.document_parsers import default_native_parsers
        # Task acceptance commits independently. A killed processor leaves a
        # durable accepted task; duplicate delivery revalidates current access.
        with self._sessions() as s,s.begin():
            _,_,row=self._input_project(s,project_id,"parse",True)
            if str(version_id) not in links(s,self.tenant_id,row.project_version_id): raise LookupError("document input not attached")
            if self.storage is None:
                raise DocumentCapabilityError("CAPABILITY_NOT_CONFIGURED: document parse storage")
            child=lambda: joined_sessions(s.connection())
            repo=PostgresDocumentIntelligenceRepository(child,self._context)
            task=repo.create_parse_task(document_version_id=version_id,idempotency_key=f"document-input:{version_id}",parser_profile_id="native-v1")
            if task["status"]=="COMPLETED": return self._input_view(s,project_id,row)
            self._draft(row,request.expected_version)
            task_id=UUID(str(task["task_id"]))
        error_code=None
        try:
            with self._sessions() as s,s.begin():
                _,_,row=self._input_project(s,project_id,"parse",True)
                self._draft(row,request.expected_version)
                if str(version_id) not in links(s,self.tenant_id,row.project_version_id): raise LookupError("document input not attached")
                s.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),{"key":f"document-parse:{self.tenant_id}:{version_id}"})
                child=lambda: joined_sessions(s.connection())
                repo=PostgresDocumentIntelligenceRepository(child,self._context)
                version=repo.get_document_version(version_id)
                content=self.storage.get(str(version["storage_ref"]))
                if hashlib.sha256(content).hexdigest()!=version["content_hash"] or len(content)!=version["size_bytes"]:
                    raise ValueError("BINARY_HASH_MISMATCH")
                class DurableReceipt:
                    def enqueue(receipt, *, task_id, task_type):
                        if task_type!="DOCUMENT_PARSE" or repo.get_parse_task(task_id) is None:
                            raise LookupError("durable parse receipt missing")
                service=DocumentParseService(repo,self.storage,default_native_parsers(),DurableReceipt())
                service.process_task(task_id)
                return self._input_view(s,project_id,row)
        except (IntakeConflict,LookupError,PermissionError):
            raise
        except Exception as exc:
            import logging, traceback
            logging.getLogger(__name__).error("Document parse technical failure: %s; frames=%s",type(exc).__name__,[(f.name,f.lineno) for f in traceback.extract_tb(exc.__traceback__)])
            error_code="BINARY_HASH_MISMATCH" if str(exc)=="BINARY_HASH_MISMATCH" else "PARSE_FAILED"
        # Partial run/structure/candidates were rolled back together. Preserve
        # a truthful failed durable task, not fabricated parse completion.
        with self._sessions() as s,s.begin():
            _,_,row=self._input_project(s,project_id,"parse",True)
            task=s.get(d.DocumentParseTaskEntity,str(task_id))
            if task.status!="COMPLETED":
                task.status="FAILED"; task.error_code=error_code
            return self._input_view(s,project_id,row)

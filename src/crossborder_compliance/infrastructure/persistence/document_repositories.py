from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import sessionmaker

from crossborder_compliance.domain.document_intelligence import (
    BusinessFactCandidate, CandidateDataFlowEdge, CandidateDataFlowNode, CandidateDataItem,
    CanonicalStructureNode, CrossDocumentLink, DocumentAnalysisSummary,
    DocumentParseQualityResult, SourceLocator, SourceTraceRef,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.document_models import (
    AnalysisSnapshotParseRunPinEntity,
    BusinessFactCandidateEntity, BusinessFactSourceLinkEntity,
    CandidateDataFlowEdgeEntity, CandidateDataFlowEdgeSourceLinkEntity,
    CandidateDataFlowNodeEntity, CandidateDataFlowNodeSourceLinkEntity,
    CandidateDataItemEntity, CandidateDataItemSourceLinkEntity,
    CanonicalStructureNodeEntity,
    CrossDocumentLinkEntity, CrossDocumentLinkSourceEntity,
    DocumentParseQualityEntity, DocumentParseRunDetailEntity, DocumentParseTaskEntity,
    DocumentVersionIntelligenceEntity, SourceTraceDetailEntity,
)
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity, DocumentEntity, DocumentParseRunEntity,
    DocumentVersionEntity, ProjectEntity, SourceTraceRefEntity,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PostgresDocumentIntelligenceRepository:
    """Tenant-scoped persistence. Phase 1B identity rows + Phase 1D 1:1 detail rows form one contract."""

    def __init__(self, session_factory: sessionmaker, context: RepositoryContext):
        self._sessions=session_factory
        self._context=context

    @property
    def tenant_id(self)->str:
        return str(self._context.tenant_id)

    def _get(self,session,model,pk,object_id:UUID):
        return session.scalar(select(model).where(pk==str(object_id),model.tenant_id==self.tenant_id))

    def create_document_version(self,*,project_id:UUID,filename:str,mime_type:str,size_bytes:int,content_hash:str,storage_ref:str)->dict[str,object]:
        with self._sessions() as s,s.begin():
            if self._get(s,ProjectEntity,ProjectEntity.project_id,project_id) is None:
                raise LookupError("project not found in tenant scope")
            document_id,version_id=uuid4(),uuid4()
            doc=DocumentEntity(document_id=str(document_id),project_id=str(project_id),tenant_id=self.tenant_id,name=filename,document_type="UPLOADED",active_version_id=None)
            s.add(doc);s.flush()
            ver=DocumentVersionEntity(document_version_id=str(version_id),document_id=str(document_id),tenant_id=self.tenant_id,version_no=1,storage_ref=storage_ref,content_hash=content_hash,mime_type=mime_type)
            s.add(ver);s.flush()
            detail=DocumentVersionIntelligenceEntity(document_version_id=str(version_id),tenant_id=self.tenant_id,filename=filename,size_bytes=size_bytes,language=None)
            s.add(detail);doc.active_version_id=str(version_id);s.flush()
            return self._version_dict(ver,detail)

    def add_document_version(self,*,document_id:UUID,filename:str,mime_type:str,size_bytes:int,content_hash:str,storage_ref:str)->dict[str,object]:
        with self._sessions() as s,s.begin():
            doc=self._get(s,DocumentEntity,DocumentEntity.document_id,document_id)
            if doc is None: raise LookupError("document not found in tenant scope")
            next_no=int(s.scalar(select(func.coalesce(func.max(DocumentVersionEntity.version_no),0)).where(DocumentVersionEntity.document_id==str(document_id),DocumentVersionEntity.tenant_id==self.tenant_id)) or 0)+1
            ver=DocumentVersionEntity(document_version_id=str(uuid4()),document_id=str(document_id),tenant_id=self.tenant_id,version_no=next_no,storage_ref=storage_ref,content_hash=content_hash,mime_type=mime_type)
            s.add(ver);s.flush()
            detail=DocumentVersionIntelligenceEntity(document_version_id=ver.document_version_id,tenant_id=self.tenant_id,filename=filename,size_bytes=size_bytes,language=None)
            s.add(detail);doc.active_version_id=ver.document_version_id;s.flush()
            return self._version_dict(ver,detail)

    def _version_dict(self,row:DocumentVersionEntity,detail:DocumentVersionIntelligenceEntity)->dict[str,object]:
        return {"document_version_id":row.document_version_id,"document_id":row.document_id,"version_no":row.version_no,
            "storage_ref":row.storage_ref,"content_hash":row.content_hash,"mime_type":row.mime_type,
            "filename":detail.filename,"size_bytes":detail.size_bytes,"language":detail.language}

    def get_document_version(self,document_version_id:UUID)->dict[str,object]|None:
        with self._sessions() as s:
            row=self._get(s,DocumentVersionEntity,DocumentVersionEntity.document_version_id,document_version_id)
            if row is None:return None
            detail=self._get(s,DocumentVersionIntelligenceEntity,DocumentVersionIntelligenceEntity.document_version_id,document_version_id)
            if detail is None:raise LookupError("document intelligence detail missing")
            return self._version_dict(row,detail)

    def create_parse_task(self,*,document_version_id:UUID,idempotency_key:str,parser_profile_id:str)->dict[str,object]:
        with self._sessions() as s,s.begin():
            if self._get(s,DocumentVersionEntity,DocumentVersionEntity.document_version_id,document_version_id) is None:
                raise LookupError("document version not found in tenant scope")
            existing=s.scalar(select(DocumentParseTaskEntity).where(
                DocumentParseTaskEntity.tenant_id==self.tenant_id,
                DocumentParseTaskEntity.document_version_id==str(document_version_id),
                DocumentParseTaskEntity.idempotency_key==idempotency_key))
            if existing:
                retry=existing.status=="FAILED"
                if retry:
                    existing.status="ACCEPTED";existing.attempts+=1;existing.error_code=None;existing.updated_at=_now()
                result=self._task_dict(existing);result["enqueue_required"]=retry;return result
            row=DocumentParseTaskEntity(task_id=str(uuid4()),tenant_id=self.tenant_id,document_version_id=str(document_version_id),
                parser_profile_id=parser_profile_id,idempotency_key=idempotency_key,status="ACCEPTED",attempts=0)
            s.add(row);s.flush();result=self._task_dict(row);result["enqueue_required"]=True;return result

    def _task_dict(self,row):
        return {"task_id":row.task_id,"document_version_id":row.document_version_id,"parser_profile_id":row.parser_profile_id,
            "idempotency_key":row.idempotency_key,"status":row.status,"attempts":row.attempts,"error_code":row.error_code}

    def get_parse_task(self,task_id:UUID)->dict[str,object]|None:
        with self._sessions() as s:
            row=self._get(s,DocumentParseTaskEntity,DocumentParseTaskEntity.task_id,task_id)
            return self._task_dict(row) if row else None

    def set_parse_task_status(self,task_id:UUID,status:str,*,error_code:str|None=None)->None:
        with self._sessions() as s,s.begin():
            row=self._get(s,DocumentParseTaskEntity,DocumentParseTaskEntity.task_id,task_id)
            if row is None:raise LookupError("parse task not found")
            row.status=status;row.error_code=error_code;row.updated_at=_now()

    def create_parse_run(self,*,document_version_id:UUID,parser_profile_id:str,parser_name:str,parser_version:str)->dict[str,object]:
        with self._sessions() as s,s.begin():
            if self._get(s,DocumentVersionEntity,DocumentVersionEntity.document_version_id,document_version_id) is None:
                raise LookupError("document version not found")
            run_no=int(s.scalar(select(func.coalesce(func.max(DocumentParseRunDetailEntity.parse_run_version),0)).where(
                DocumentParseRunDetailEntity.tenant_id==self.tenant_id,
                DocumentParseRunDetailEntity.document_version_id==str(document_version_id))) or 0)+1
            run_id=uuid4()
            base=DocumentParseRunEntity(document_parse_run_id=str(run_id),document_version_id=str(document_version_id),
                tenant_id=self.tenant_id,parser_version=f"{parser_version}#run-{run_no}",result_ref=None,status="RUNNING")
            s.add(base);s.flush()
            detail=DocumentParseRunDetailEntity(parse_run_id=str(run_id),document_version_id=str(document_version_id),tenant_id=self.tenant_id,
                parse_run_version=run_no,parser_profile_id=parser_profile_id,parser_name=parser_name,parser_version=parser_version,
                started_at=_now(),status="RUNNING",native_parse_used=False,ocr_used=False,vision_used=False,
                page_count=0,table_count=0,image_count=0,warning_count=0,provenance_json={"source":"document-parse-service"})
            s.add(detail);s.flush();return self._run_dict(base,detail)

    def _run_dict(self,base:DocumentParseRunEntity,detail:DocumentParseRunDetailEntity)->dict[str,object]:
        return {"parse_run_id":base.document_parse_run_id,"document_version_id":base.document_version_id,
            "parse_run_version":detail.parse_run_version,"parser_profile_id":detail.parser_profile_id,
            "parser_name":detail.parser_name,"parser_version":detail.parser_version,"status":detail.status,
            "native_parse_used":detail.native_parse_used,"ocr_used":detail.ocr_used,"vision_used":detail.vision_used,
            "page_count":detail.page_count,"table_count":detail.table_count,"image_count":detail.image_count,
            "warning_count":detail.warning_count,"quality_score":detail.quality_score,"error_code":detail.error_code,"language":detail.language}

    def finish_parse_run(self,parse_run_id:UUID,*,status:str,native_parse_used:bool,ocr_used:bool,vision_used:bool,
        counts:dict[str,int],quality_score:float|None,warning_count:int,error_code:str|None,language:str|None)->None:
        with self._sessions() as s,s.begin():
            base=self._get(s,DocumentParseRunEntity,DocumentParseRunEntity.document_parse_run_id,parse_run_id)
            detail=self._get(s,DocumentParseRunDetailEntity,DocumentParseRunDetailEntity.parse_run_id,parse_run_id)
            if base is None or detail is None:raise LookupError("parse run not found")
            base.status=status;base.updated_at=_now()
            detail.status=status;detail.completed_at=_now();detail.native_parse_used=native_parse_used;detail.ocr_used=ocr_used;detail.vision_used=vision_used
            detail.page_count=counts.get("page_count",0);detail.table_count=counts.get("table_count",0);detail.image_count=counts.get("image_count",0)
            detail.warning_count=warning_count;detail.quality_score=quality_score;detail.error_code=error_code;detail.language=language;detail.updated_at=_now()

    def list_parse_runs(self,document_version_id:UUID)->list[dict[str,object]]:
        with self._sessions() as s:
            details=s.scalars(select(DocumentParseRunDetailEntity).where(
                DocumentParseRunDetailEntity.tenant_id==self.tenant_id,
                DocumentParseRunDetailEntity.document_version_id==str(document_version_id)
            ).order_by(DocumentParseRunDetailEntity.parse_run_version)).all()
            out=[]
            for d in details:
                base=self._get(s,DocumentParseRunEntity,DocumentParseRunEntity.document_parse_run_id,UUID(d.parse_run_id))
                if base:out.append(self._run_dict(base,d))
            return out

    def get_parse_run(self,parse_run_id:UUID)->dict[str,object]|None:
        with self._sessions() as s:
            base=self._get(s,DocumentParseRunEntity,DocumentParseRunEntity.document_parse_run_id,parse_run_id)
            detail=self._get(s,DocumentParseRunDetailEntity,DocumentParseRunDetailEntity.parse_run_id,parse_run_id)
            return self._run_dict(base,detail) if base and detail else None

    def replace_structure(self,parse_run_id:UUID,nodes)->list[SourceTraceRef]:
        with self._sessions() as s,s.begin():
            run=self._get(s,DocumentParseRunEntity,DocumentParseRunEntity.document_parse_run_id,parse_run_id)
            if run is None:raise LookupError("parse run not found")
            ver=self._get(s,DocumentVersionEntity,DocumentVersionEntity.document_version_id,UUID(run.document_version_id))
            if ver is None:raise LookupError("document version not found")
            trace_ids=select(SourceTraceDetailEntity.source_trace_ref_id).where(SourceTraceDetailEntity.tenant_id==self.tenant_id,SourceTraceDetailEntity.parse_run_id==str(parse_run_id))
            s.query(SourceTraceRefEntity).filter(SourceTraceRefEntity.source_trace_ref_id.in_(trace_ids)).delete(synchronize_session=False)
            s.query(CanonicalStructureNodeEntity).filter(CanonicalStructureNodeEntity.tenant_id==self.tenant_id,CanonicalStructureNodeEntity.parse_run_id==str(parse_run_id)).delete(synchronize_session=False)
            node_list=list(nodes)
            for n in node_list:
                s.add(CanonicalStructureNodeEntity(structure_node_id=str(n.structure_node_id),parse_run_id=str(parse_run_id),
                    document_version_id=str(n.document_version_id),tenant_id=self.tenant_id,node_type=n.node_type.value,
                    parent_node_id=str(n.parent_node_id) if n.parent_node_id else None,sequence=n.sequence,page_no=n.page_no,
                    sheet_name=n.sheet_name,slide_no=n.slide_no,section_path=n.section_path,bbox_json=list(n.bbox) if n.bbox else None,
                    original_text=n.original_text,normalized_text=n.normalized_text,language=n.language,source_locator_json=n.source_locator,
                    parser_confidence=n.parser_confidence,provenance_json=n.provenance,metadata_json=n.metadata))
            s.flush()
            traces=[]
            for n in node_list:
                trace_id=uuid4()
                locator=SourceLocator(page_no=n.page_no,sheet_name=n.sheet_name,slide_no=n.slide_no,section_path=n.section_path,
                    table_id=str(n.metadata.get("table_id")) if n.metadata.get("table_id") else None,
                    row_index=n.metadata.get("row_index"),column_index=n.metadata.get("column_index"),bbox=n.bbox)
                text_hash=hashlib.sha256((n.original_text or "").encode("utf-8")).hexdigest()
                base_trace=SourceTraceRefEntity(source_trace_ref_id=str(trace_id),tenant_id=self.tenant_id,
                    document_version_id=ver.document_version_id,page_no=n.page_no,section=n.section_path,
                    table_ref=locator.table_id,row_ref=str(locator.row_index) if locator.row_index is not None else None,
                    bbox_json=list(n.bbox) if n.bbox else None)
                s.add(base_trace);s.flush()
                s.add(SourceTraceDetailEntity(source_trace_ref_id=str(trace_id),tenant_id=self.tenant_id,document_id=ver.document_id,
                    parse_run_id=str(parse_run_id),structure_node_id=str(n.structure_node_id),sheet_name=n.sheet_name,
                    slide_no=n.slide_no,section_path=n.section_path,table_id=locator.table_id,row_index=locator.row_index,
                    column_index=locator.column_index,original_text_hash=text_hash))
                traces.append(SourceTraceRef(trace_id,UUID(ver.document_id),UUID(ver.document_version_id),parse_run_id,n.structure_node_id,locator,text_hash))
            return traces

    def list_structure(self,parse_run_id:UUID)->list[dict[str,object]]:
        with self._sessions() as s:
            rows=s.scalars(select(CanonicalStructureNodeEntity).where(
                CanonicalStructureNodeEntity.tenant_id==self.tenant_id,
                CanonicalStructureNodeEntity.parse_run_id==str(parse_run_id)
            ).order_by(CanonicalStructureNodeEntity.sequence)).all()
            return [{"structure_node_id":r.structure_node_id,"node_type":r.node_type,"parent_node_id":r.parent_node_id,
                "sequence":r.sequence,"page_no":r.page_no,"sheet_name":r.sheet_name,"slide_no":r.slide_no,
                "section_path":r.section_path,"bbox":r.bbox_json,"original_text":r.original_text,"normalized_text":r.normalized_text,
                "language":r.language,"source_locator":r.source_locator_json,"parser_confidence":r.parser_confidence,"metadata":r.metadata_json} for r in rows]

    def save_quality(self,result:DocumentParseQualityResult)->None:
        with self._sessions() as s,s.begin():
            s.add(DocumentParseQualityEntity(quality_result_id=str(result.quality_result_id),parse_run_id=str(result.parse_run_id),
                tenant_id=self.tenant_id,text_coverage=result.text_coverage,page_coverage=result.page_coverage,
                table_extraction_quality=result.table_extraction_quality,ocr_confidence=result.ocr_confidence,
                layout_quality=result.layout_quality,structural_completeness=result.structural_completeness,
                language_detection_confidence=result.language_detection_confidence,quality_status=result.status.value,quality_score=result.score))

    def get_quality(self,parse_run_id:UUID)->dict[str,object]|None:
        with self._sessions() as s:
            r=s.scalar(select(DocumentParseQualityEntity).where(DocumentParseQualityEntity.tenant_id==self.tenant_id,DocumentParseQualityEntity.parse_run_id==str(parse_run_id)))
            return None if not r else {"parse_run_id":r.parse_run_id,"status":r.quality_status,"score":r.quality_score,
                "text_coverage":r.text_coverage,"page_coverage":r.page_coverage,"table_extraction_quality":r.table_extraction_quality,
                "ocr_confidence":r.ocr_confidence,"layout_quality":r.layout_quality,"structural_completeness":r.structural_completeness,
                "language_detection_confidence":r.language_detection_confidence}

    def _link_sources(self,s,model,id_field,parent_id,refs):
        for trace in refs:
            s.add(model(**{id_field:str(uuid4()),parent_id[0]:str(parent_id[1]),"source_trace_ref_id":str(trace.source_trace_ref_id),"tenant_id":self.tenant_id}))

    def save_fact(self,parse_run_id:UUID,fact:BusinessFactCandidate)->None:
        if not fact.source_trace_refs:raise ValueError("formal extracted candidate requires SourceTraceRef")
        with self._sessions() as s,s.begin():
            s.add(BusinessFactCandidateEntity(fact_id=str(fact.fact_id),parse_run_id=str(parse_run_id),tenant_id=self.tenant_id,
                fact_type=fact.fact_type,normalized_value_json=fact.normalized_value,original_value_json=fact.original_value,
                extraction_method=fact.extraction_method,confidence=fact.confidence,validation_status=fact.validation_status.value,
                conflict_status=fact.conflict_status.value))
            self._link_sources(s,BusinessFactSourceLinkEntity,"business_fact_source_link_id",("fact_id",fact.fact_id),fact.source_trace_refs)

    def save_candidate_item(self,parse_run_id:UUID,item:CandidateDataItem)->None:
        if not item.source_trace_refs:raise ValueError("candidate data item requires SourceTraceRef")
        with self._sessions() as s,s.begin():
            s.add(CandidateDataItemEntity(candidate_data_item_id=str(item.candidate_data_item_id),parse_run_id=str(parse_run_id),
                tenant_id=self.tenant_id,raw_name=item.raw_name,normalized_name=item.normalized_name,description=item.description,
                value_type=item.value_type,unit=item.unit,quantity_metadata_json=item.quantity_metadata,system_ref=item.system_ref,confidence=item.confidence))
            self._link_sources(s,CandidateDataItemSourceLinkEntity,"candidate_data_item_source_link_id",("candidate_data_item_id",item.candidate_data_item_id),item.source_trace_refs)

    def save_candidate_flow_node(self,parse_run_id:UUID,node:CandidateDataFlowNode)->None:
        if not node.source_trace_refs:raise ValueError("candidate flow node requires SourceTraceRef")
        with self._sessions() as s,s.begin():
            s.add(CandidateDataFlowNodeEntity(candidate_node_id=str(node.candidate_node_id),parse_run_id=str(parse_run_id),
                tenant_id=self.tenant_id,name=node.name,node_type_candidate=node.node_type_candidate,location_candidate=node.location_candidate,
                party_candidate=node.party_candidate,system_candidate=node.system_candidate,confidence=node.confidence))
            self._link_sources(s,CandidateDataFlowNodeSourceLinkEntity,"candidate_data_flow_node_source_link_id",("candidate_node_id",node.candidate_node_id),node.source_trace_refs)

    def save_candidate_flow_edge(self,parse_run_id:UUID,edge:CandidateDataFlowEdge)->None:
        if not edge.source_trace_refs:raise ValueError("candidate flow edge requires SourceTraceRef")
        with self._sessions() as s,s.begin():
            s.add(CandidateDataFlowEdgeEntity(candidate_edge_id=str(edge.candidate_edge_id),parse_run_id=str(parse_run_id),
                tenant_id=self.tenant_id,source_candidate_node_id=str(edge.source_candidate_node_id),target_candidate_node_id=str(edge.target_candidate_node_id),
                direction=edge.direction,transfer_type_candidate=edge.transfer_type_candidate,data_item_refs_json=[str(x) for x in edge.data_item_refs],confidence=edge.confidence))
            self._link_sources(s,CandidateDataFlowEdgeSourceLinkEntity,"candidate_data_flow_edge_source_link_id",("candidate_edge_id",edge.candidate_edge_id),edge.source_trace_refs)

    def list_facts(self,parse_run_id:UUID)->list[dict[str,object]]:
        with self._sessions() as s:
            rows=s.scalars(select(BusinessFactCandidateEntity).where(BusinessFactCandidateEntity.tenant_id==self.tenant_id,BusinessFactCandidateEntity.parse_run_id==str(parse_run_id))).all()
            return [{"fact_id":r.fact_id,"fact_type":r.fact_type,"normalized_value":r.normalized_value_json,"original_value":r.original_value_json,
                "confidence":r.confidence,"validation_status":r.validation_status,"conflict_status":r.conflict_status} for r in rows]

    def list_candidate_items(self,parse_run_id:UUID)->list[dict[str,object]]:
        with self._sessions() as s:
            rows=s.scalars(select(CandidateDataItemEntity).where(CandidateDataItemEntity.tenant_id==self.tenant_id,CandidateDataItemEntity.parse_run_id==str(parse_run_id))).all()
            return [{"candidate_data_item_id":r.candidate_data_item_id,"raw_name":r.raw_name,"normalized_name":r.normalized_name,
                "value_type":r.value_type,"unit":r.unit,"confidence":r.confidence} for r in rows]

    def list_candidate_flows(self,parse_run_id:UUID)->dict[str,list[dict[str,object]]]:
        with self._sessions() as s:
            nodes=s.scalars(select(CandidateDataFlowNodeEntity).where(CandidateDataFlowNodeEntity.tenant_id==self.tenant_id,CandidateDataFlowNodeEntity.parse_run_id==str(parse_run_id))).all()
            edges=s.scalars(select(CandidateDataFlowEdgeEntity).where(CandidateDataFlowEdgeEntity.tenant_id==self.tenant_id,CandidateDataFlowEdgeEntity.parse_run_id==str(parse_run_id))).all()
            return {"nodes":[{"candidate_node_id":r.candidate_node_id,"name":r.name,"type":r.node_type_candidate,"confidence":r.confidence} for r in nodes],
                "edges":[{"candidate_edge_id":r.candidate_edge_id,"source":r.source_candidate_node_id,"target":r.target_candidate_node_id,
                    "direction":r.direction,"transfer_type":r.transfer_type_candidate,"confidence":r.confidence} for r in edges]}

    def save_cross_document_link(self,project_id:UUID,link:CrossDocumentLink)->None:
        if not link.source_trace_refs:raise ValueError("cross-document link requires evidence")
        with self._sessions() as s,s.begin():
            if self._get(s,ProjectEntity,ProjectEntity.project_id,project_id) is None:raise LookupError("project not found")
            s.add(CrossDocumentLinkEntity(cross_document_link_id=str(link.cross_document_link_id),project_id=str(project_id),
                tenant_id=self.tenant_id,link_type=link.link_type,left_object_type=link.left_object_type,left_object_id=str(link.left_object_id),
                right_object_type=link.right_object_type,right_object_id=str(link.right_object_id),confidence=link.confidence))
            for trace in link.source_trace_refs:
                s.add(CrossDocumentLinkSourceEntity(cross_document_link_source_id=str(uuid4()),cross_document_link_id=str(link.cross_document_link_id),
                    source_trace_ref_id=str(trace.source_trace_ref_id),tenant_id=self.tenant_id))

    def pin_parse_run(self,*,analysis_snapshot_id:UUID,document_version_id:UUID,parse_run_id:UUID)->None:
        with self._sessions() as s,s.begin():
            snap=self._get(s,AnalysisSnapshotEntity,AnalysisSnapshotEntity.analysis_snapshot_id,analysis_snapshot_id)
            run=self._get(s,DocumentParseRunEntity,DocumentParseRunEntity.document_parse_run_id,parse_run_id)
            if snap is None or run is None or run.document_version_id!=str(document_version_id):
                raise LookupError("snapshot/parse run not found in tenant scope")
            existing=s.scalar(select(AnalysisSnapshotParseRunPinEntity).where(
                AnalysisSnapshotParseRunPinEntity.tenant_id==self.tenant_id,
                AnalysisSnapshotParseRunPinEntity.analysis_snapshot_id==str(analysis_snapshot_id),
                AnalysisSnapshotParseRunPinEntity.document_version_id==str(document_version_id)))
            if existing:
                if existing.parse_run_id!=str(parse_run_id):raise ValueError("analysis snapshot parse-run pin is immutable")
                return
            s.add(AnalysisSnapshotParseRunPinEntity(pin_id=str(uuid4()),analysis_snapshot_id=str(analysis_snapshot_id),
                document_version_id=str(document_version_id),parse_run_id=str(parse_run_id),tenant_id=self.tenant_id))

    def aggregate_project_summary(self,project_id:UUID)->DocumentAnalysisSummary:
        with self._sessions() as s:
            if self._get(s,ProjectEntity,ProjectEntity.project_id,project_id) is None:raise LookupError("project not found")
            docs=select(DocumentEntity.document_id).where(DocumentEntity.tenant_id==self.tenant_id,DocumentEntity.project_id==str(project_id))
            versions=select(DocumentVersionEntity.document_version_id).join(DocumentEntity,DocumentEntity.document_id==DocumentVersionEntity.document_id).where(
                DocumentVersionEntity.tenant_id==self.tenant_id,DocumentEntity.project_id==str(project_id))
            runs=select(DocumentParseRunDetailEntity.parse_run_id).where(
                DocumentParseRunDetailEntity.tenant_id==self.tenant_id,DocumentParseRunDetailEntity.document_version_id.in_(versions))
            def node_count(kind):
                return int(s.scalar(select(func.count()).select_from(CanonicalStructureNodeEntity).where(
                    CanonicalStructureNodeEntity.tenant_id==self.tenant_id,CanonicalStructureNodeEntity.parse_run_id.in_(runs),
                    CanonicalStructureNodeEntity.node_type==kind)) or 0)
            raw_fields=int(s.scalar(select(func.count()).select_from(CanonicalStructureNodeEntity).where(
                CanonicalStructureNodeEntity.tenant_id==self.tenant_id,CanonicalStructureNodeEntity.parse_run_id.in_(runs),
                CanonicalStructureNodeEntity.node_type=="TABLE_CELL",CanonicalStructureNodeEntity.metadata_json["header"].as_boolean()==True)) or 0)
            return DocumentAnalysisSummary(
                document_count=int(s.scalar(select(func.count()).select_from(docs.subquery())) or 0),
                document_version_count=int(s.scalar(select(func.count()).select_from(versions.subquery())) or 0),
                page_count=node_count("PAGE"),sheet_count=node_count("SHEET"),slide_count=node_count("SLIDE"),table_count=node_count("TABLE"),
                raw_field_count=raw_fields,
                normalized_candidate_data_item_count=int(s.scalar(select(func.count(distinct(CandidateDataItemEntity.normalized_name))).where(
                    CandidateDataItemEntity.tenant_id==self.tenant_id,CandidateDataItemEntity.parse_run_id.in_(runs))) or 0),
                candidate_data_flow_count=int(s.scalar(select(func.count()).select_from(CandidateDataFlowEdgeEntity).where(
                    CandidateDataFlowEdgeEntity.tenant_id==self.tenant_id,CandidateDataFlowEdgeEntity.parse_run_id.in_(runs))) or 0),
                diagram_count=node_count("DIAGRAM"),
                unresolved_fact_count=int(s.scalar(select(func.count()).select_from(BusinessFactCandidateEntity).where(
                    BusinessFactCandidateEntity.tenant_id==self.tenant_id,BusinessFactCandidateEntity.parse_run_id.in_(runs),
                    BusinessFactCandidateEntity.validation_status.in_(["UNVALIDATED","REVIEW_REQUIRED"]))) or 0),
                conflict_count=int(s.scalar(select(func.count()).select_from(BusinessFactCandidateEntity).where(
                    BusinessFactCandidateEntity.tenant_id==self.tenant_id,BusinessFactCandidateEntity.parse_run_id.in_(runs),
                    BusinessFactCandidateEntity.conflict_status!="NONE")) or 0),
                review_required_count=int(s.scalar(select(func.count()).select_from(DocumentParseQualityEntity).where(
                    DocumentParseQualityEntity.tenant_id==self.tenant_id,DocumentParseQualityEntity.parse_run_id.in_(runs),
                    DocumentParseQualityEntity.quality_status=="REVIEW_REQUIRED")) or 0),
                parsing_warning_count=int(s.scalar(select(func.coalesce(func.sum(DocumentParseRunDetailEntity.warning_count),0)).where(
                    DocumentParseRunDetailEntity.tenant_id==self.tenant_id,DocumentParseRunDetailEntity.parse_run_id.in_(runs))) or 0),
            )

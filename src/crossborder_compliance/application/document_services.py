from __future__ import annotations

import hashlib
import mimetypes
import re
from dataclasses import replace
from pathlib import PurePath
from uuid import UUID, uuid4

from crossborder_compliance.application.document_ports import (
    DocumentIntelligenceRepositoryPort,
    DocumentParserPort,
    MalwareScanPort,
    ObjectStoragePort,
    TaskQueuePort,
    VisionDiagramPort,
)
from crossborder_compliance.domain.document_intelligence import (
    BusinessFactCandidate,
    CandidateDataFlowEdge,
    CandidateDataFlowNode,
    CandidateDataItem,
    CandidateValidationStatus,
    CanonicalNodeType,
    ConflictStatus,
    CrossDocumentLink,
    DocumentParseQualityResult,
    ParseQualityStatus,
    SourceTraceRef,
)


_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv", ".pptx", ".txt", ".png", ".jpg", ".jpeg"}
_ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "image/png",
    "image/jpeg",
}


class DocumentValidationError(ValueError): pass
class ParserNotFoundError(LookupError): pass
class ParseQualityGateError(RuntimeError): pass


def normalize_filename(filename: str) -> str:
    name = PurePath(filename.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._() -]+", "_", name).strip()
    if not name or name in {".", ".."}:
        raise DocumentValidationError("invalid filename")
    return name[:255]


class DocumentIngestionService:
    def __init__(self, repository: DocumentIntelligenceRepositoryPort, storage: ObjectStoragePort, malware_scan: MalwareScanPort, *, max_size_bytes: int = 50 * 1024 * 1024):
        self.repository = repository
        self.storage = storage
        self.malware_scan = malware_scan
        self.max_size_bytes = max_size_bytes

    def _validate(self, filename: str, mime_type: str, content: bytes) -> str:
        safe = normalize_filename(filename)
        ext = PurePath(safe).suffix.lower()
        if ext not in _ALLOWED_EXTENSIONS:
            raise DocumentValidationError("unsupported extension")
        if mime_type not in _ALLOWED_MIME:
            raise DocumentValidationError("unsupported MIME type")
        guessed = mimetypes.guess_type(safe)[0]
        if guessed and guessed != mime_type and not ({guessed, mime_type} <= {"image/jpeg", "image/jpg"}):
            raise DocumentValidationError("extension/MIME mismatch")
        if not content or len(content) > self.max_size_bytes:
            raise DocumentValidationError("invalid file size")
        if not self.malware_scan.scan(content=content, filename=safe):
            raise DocumentValidationError("malware scan failed")
        return safe

    def ingest(self, *, tenant_id: UUID, project_id: UUID, filename: str, mime_type: str, content: bytes) -> dict[str, object]:
        safe = self._validate(filename, mime_type, content)
        digest = hashlib.sha256(content).hexdigest()
        object_key = f"tenant/{tenant_id}/project/{project_id}/documents/{uuid4()}/{safe}"
        storage_ref = self.storage.put(object_key=object_key, content=content, content_type=mime_type)
        return self.repository.create_document_version(project_id=project_id, filename=safe, mime_type=mime_type, size_bytes=len(content), content_hash=digest, storage_ref=storage_ref)

    def add_version(self, *, tenant_id: UUID, document_id: UUID, filename: str, mime_type: str, content: bytes) -> dict[str, object]:
        safe = self._validate(filename, mime_type, content)
        digest = hashlib.sha256(content).hexdigest()
        object_key = f"tenant/{tenant_id}/document/{document_id}/versions/{uuid4()}/{safe}"
        storage_ref = self.storage.put(object_key=object_key, content=content, content_type=mime_type)
        return self.repository.add_document_version(document_id=document_id, filename=safe, mime_type=mime_type, size_bytes=len(content), content_hash=digest, storage_ref=storage_ref)


class DocumentParseService:
    def __init__(self, repository: DocumentIntelligenceRepositoryPort, storage: ObjectStoragePort, parsers: list[DocumentParserPort], task_queue: TaskQueuePort, *, vision: VisionDiagramPort | None = None):
        self.repository = repository
        self.storage = storage
        self.parsers = parsers
        self.task_queue = task_queue
        self.vision = vision

    def request_parse(self, *, document_version_id: UUID, idempotency_key: str, parser_profile_id: str = "default") -> dict[str, object]:
        task = self.repository.create_parse_task(document_version_id=document_version_id, idempotency_key=idempotency_key, parser_profile_id=parser_profile_id)
        if task.get("status") == "ACCEPTED":
            self.task_queue.enqueue(task_id=UUID(str(task["task_id"])), task_type="DOCUMENT_PARSE")
        return task

    def process_task(self, task_id: UUID) -> dict[str, object]:
        task = self.repository.get_parse_task(task_id)
        if not task:
            raise LookupError("parse task not found")
        if task["status"] == "COMPLETED":
            return task
        self.repository.set_parse_task_status(task_id, "RUNNING")
        version = self.repository.get_document_version(UUID(str(task["document_version_id"])))
        if not version:
            self.repository.set_parse_task_status(task_id, "FAILED", error_code="DOCUMENT_VERSION_NOT_FOUND")
            raise LookupError("document version not found")
        content = self.storage.get(str(version["storage_ref"]))
        parser = next((p for p in self.parsers if p.supports(mime_type=str(version["mime_type"]), filename=str(version["filename"]))), None)
        if parser is None:
            self.repository.set_parse_task_status(task_id, "FAILED", error_code="PARSER_NOT_FOUND")
            raise ParserNotFoundError(str(version["mime_type"]))
        run = self.repository.create_parse_run(
            document_version_id=UUID(str(version["document_version_id"])),
            parser_profile_id=str(task["parser_profile_id"]),
            parser_name=parser.parser_name,
            parser_version=parser.parser_version,
        )
        run_id = UUID(str(run["parse_run_id"]))
        try:
            parsed = parser.parse(document_version_id=UUID(str(version["document_version_id"])), content=content, filename=str(version["filename"]), mime_type=str(version["mime_type"]))
            traces = self.repository.replace_structure(run_id, parsed.nodes)
            quality = self._quality(run_id, parsed, traces)
            self.repository.save_quality(quality)
            self._extract_candidates(run_id, parsed.nodes, traces)
            counts = {
                "page_count": sum(n.node_type == CanonicalNodeType.PAGE for n in parsed.nodes),
                "table_count": sum(n.node_type == CanonicalNodeType.TABLE for n in parsed.nodes),
                "image_count": sum(n.node_type in {CanonicalNodeType.IMAGE, CanonicalNodeType.DIAGRAM} for n in parsed.nodes),
            }
            self.repository.finish_parse_run(run_id, status="COMPLETED", native_parse_used=parsed.native_parse_used, ocr_used=parsed.ocr_used, vision_used=parsed.vision_used, counts=counts, quality_score=quality.score, warning_count=len(parsed.warnings), error_code=None, language=parsed.detected_language)
            self.repository.set_parse_task_status(task_id, "COMPLETED")
            return self.repository.get_parse_run(run_id) or run
        except Exception:
            self.repository.finish_parse_run(run_id, status="FAILED", native_parse_used=False, ocr_used=False, vision_used=False, counts={}, quality_score=None, warning_count=1, error_code="PARSE_FAILED", language=None)
            self.repository.set_parse_task_status(task_id, "FAILED", error_code="PARSE_FAILED")
            raise

    def _quality(self, parse_run_id: UUID, parsed, traces: list[SourceTraceRef]) -> DocumentParseQualityResult:
        text_nodes = [n for n in parsed.nodes if n.node_type in {CanonicalNodeType.PARAGRAPH, CanonicalNodeType.HEADING, CanonicalNodeType.TABLE_CELL}]
        text_nonempty = sum(bool((n.normalized_text or n.original_text or "").strip()) for n in text_nodes)
        text_coverage = 1.0 if not text_nodes else text_nonempty / len(text_nodes)
        page_nodes = [n for n in parsed.nodes if n.node_type == CanonicalNodeType.PAGE]
        page_coverage = 1.0 if page_nodes or any(n.sheet_name or n.slide_no for n in parsed.nodes) else 0.5
        table_cells = [n for n in parsed.nodes if n.node_type == CanonicalNodeType.TABLE_CELL]
        table_quality = 1.0 if table_cells else 0.8
        layout = 1.0 if all(n.sequence >= 0 for n in parsed.nodes) else 0.0
        structural = min(1.0, len(traces) / max(1, len(parsed.nodes)))
        language_conf = 1.0 if parsed.detected_language else 0.6
        ocr_conf = None
        if parsed.ocr_used:
            values = [float(n.metadata.get("ocr_confidence", 0.0)) for n in parsed.nodes if "ocr_confidence" in n.metadata]
            ocr_conf = sum(values) / len(values) if values else 0.5
        components = [text_coverage, page_coverage, table_quality, layout, structural, language_conf]
        if ocr_conf is not None:
            components.append(ocr_conf)
        score = sum(components) / len(components)
        if score < 0.35:
            status = ParseQualityStatus.FAILED
        elif score < 0.65 or (ocr_conf is not None and ocr_conf < 0.6):
            status = ParseQualityStatus.REVIEW_REQUIRED
        elif score < 0.8 or parsed.warnings:
            status = ParseQualityStatus.WARNING
        else:
            status = ParseQualityStatus.PASS
        return DocumentParseQualityResult(uuid4(), parse_run_id, text_coverage, page_coverage, table_quality, ocr_conf, layout, structural, language_conf, status, score)

    def _extract_candidates(self, parse_run_id: UUID, nodes, traces: list[SourceTraceRef]) -> None:
        trace_by_node = {t.structure_node_id: t for t in traces}
        for node in nodes:
            trace = trace_by_node.get(node.structure_node_id)
            if not trace:
                continue
            text = (node.normalized_text or node.original_text or "").strip()
            if node.node_type == CanonicalNodeType.TABLE_CELL and node.metadata.get("header") and text:
                self.repository.save_candidate_item(parse_run_id, CandidateDataItem(
                    candidate_data_item_id=uuid4(), raw_name=text, normalized_name=re.sub(r"\s+", " ", text).strip().casefold(),
                    description=None, value_type=None, unit=node.metadata.get("unit"), quantity_metadata={},
                    system_ref=None, source_trace_refs=(trace,), confidence=float(node.parser_confidence or 0.9),
                ))
            if node.node_type == CanonicalNodeType.PARAGRAPH and ":" in text:
                key, value = [part.strip() for part in text.split(":", 1)]
                if key and value:
                    self.repository.save_fact(parse_run_id, BusinessFactCandidate(
                        fact_id=uuid4(), fact_type=str(node.metadata.get("fact_type", "GENERIC_FIELD")),
                        normalized_value=value, original_value=value, source_trace_refs=(trace,),
                        extraction_method="STRUCTURED_TEXT", confidence=float(node.parser_confidence or 0.8),
                        validation_status=CandidateValidationStatus.UNVALIDATED, conflict_status=ConflictStatus.NONE,
                    ))
            if node.node_type == CanonicalNodeType.DIAGRAM:
                for dn in node.metadata.get("candidate_nodes", []):
                    self.repository.save_candidate_flow_node(parse_run_id, CandidateDataFlowNode(
                        candidate_node_id=UUID(str(dn["candidate_node_id"])), name=str(dn["label"]),
                        node_type_candidate=dn.get("node_type_candidate"), location_candidate=None, party_candidate=None,
                        system_candidate=None, source_trace_refs=(trace,), confidence=float(dn.get("confidence", 0.5)),
                    ))
                for de in node.metadata.get("candidate_edges", []):
                    self.repository.save_candidate_flow_edge(parse_run_id, CandidateDataFlowEdge(
                        candidate_edge_id=UUID(str(de["candidate_edge_id"])),
                        source_candidate_node_id=UUID(str(de["source_candidate_node_id"])),
                        target_candidate_node_id=UUID(str(de["target_candidate_node_id"])),
                        direction=de.get("direction"), transfer_type_candidate=de.get("relation"),
                        data_item_refs=(), source_trace_refs=(trace,), confidence=float(de.get("confidence", 0.5)),
                    ))


class DocumentAnalysisService:
    def __init__(self, repository: DocumentIntelligenceRepositoryPort):
        self.repository = repository

    def summary(self, project_id: UUID):
        return self.repository.aggregate_project_summary(project_id)

    def pin_parse_run(self, *, analysis_snapshot_id: UUID, document_version_id: UUID, parse_run_id: UUID) -> None:
        self.repository.pin_parse_run(analysis_snapshot_id=analysis_snapshot_id, document_version_id=document_version_id, parse_run_id=parse_run_id)


class CrossDocumentLinkingService:
    """Evidence-backed generic linker. It never links on filename alone."""

    def __init__(self, repository: DocumentIntelligenceRepositoryPort):
        self.repository = repository

    def link_same_normalized_candidate(
        self,
        *,
        project_id: UUID,
        left_object_id: UUID,
        right_object_id: UUID,
        left_normalized_name: str,
        right_normalized_name: str,
        left_trace: SourceTraceRef,
        right_trace: SourceTraceRef,
        object_type: str = "CANDIDATE_DATA_ITEM",
    ) -> CrossDocumentLink | None:
        left = re.sub(r"\s+", " ", left_normalized_name).strip().casefold()
        right = re.sub(r"\s+", " ", right_normalized_name).strip().casefold()
        if not left or left != right:
            return None
        link = CrossDocumentLink(
            cross_document_link_id=uuid4(),
            link_type="SAME_NORMALIZED_CANDIDATE",
            left_object_type=object_type,
            left_object_id=left_object_id,
            right_object_type=object_type,
            right_object_id=right_object_id,
            confidence=1.0,
            source_trace_refs=(left_trace, right_trace),
        )
        self.repository.save_cross_document_link(project_id, link)
        return link

"""Semantic enhancement of genuine parser output into canonical candidates only."""

from uuid import uuid4

from crossborder_compliance.domain.document_intelligence import (
    BusinessFactCandidate,
    CandidateDataFlowEdge,
    CandidateDataFlowNode,
    CandidateDataItem,
    CandidateValidationStatus,
)
from crossborder_compliance.domain.llm_document_candidates import DocumentCandidateExtraction
from crossborder_compliance.domain.llm_invocation import InvocationFacts


class DocumentSemanticExtractionService:
    def __init__(
        self, repository, invocation, request, bind_input, *, fact_types, minimum_confidence
    ):
        self.repository, self.invocation, self.request = repository, invocation, request
        self.bind_input, self.fact_types = bind_input, fact_types
        self.minimum_confidence = minimum_confidence

    def enhance(self, run_id, nodes, traces):
        # Native structured extraction remains preferred. The semantic route is
        # an enhancement for otherwise unstructured input, not a second parser.
        if (
            self.repository.list_facts(run_id)
            or self.repository.list_candidate_items(run_id)
            or self.repository.list_candidate_flows(run_id)["edges"]
        ):
            return False
        textual = [node for node in nodes if node.original_text or node.normalized_text]
        if not textual:
            return False
        ref = self.bind_input(run_id, textual)
        result = self.invocation.invoke(
            self.request.model_copy(update={"input_refs": (ref,)}),
            InvocationFacts(
                trigger="DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED",
                purpose="DOCUMENT_CANDIDATE_EXTRACTION",
                parser_insufficient=True,
            ),
        )
        self.repository.record_semantic_provenance(run_id, result)
        by_node = {trace.structure_node_id: trace for trace in traces}
        text_by_node = {
            node.structure_node_id: node.original_text or node.normalized_text for node in nodes
        }
        review = result.status != "COMPLETED"
        for outcome in result.model_results:
            if outcome.result is None:
                continue
            output = DocumentCandidateExtraction.model_validate(outcome.result.result.structured)
            all_rows = (*output.facts, *output.items, *output.nodes, *output.edges)
            if any(row.source_node_id not in by_node for row in all_rows):
                review = True
                continue  # Never manufacture a trace for an invalid source locator.
            review |= any(row.confidence < self.minimum_confidence for row in all_rows)
            for fact in output.facts:
                if fact.fact_type not in self.fact_types:
                    review = True
                    continue
                self.repository.save_fact(
                    run_id,
                    BusinessFactCandidate(
                        fact_id=uuid4(),
                        fact_type=fact.fact_type,
                        normalized_value=fact.value,
                        original_value=text_by_node[fact.source_node_id],
                        source_trace_refs=(by_node[fact.source_node_id],),
                        extraction_method="LLM_STRUCTURED_OUTPUT",
                        confidence=fact.confidence,
                        validation_status=CandidateValidationStatus.UNVALIDATED,
                    ),
                )
            for item in output.items:
                self.repository.save_candidate_item(
                    run_id,
                    CandidateDataItem(
                        uuid4(),
                        item.name,
                        " ".join(item.name.casefold().split()),
                        item.description,
                        None,
                        None,
                        {},
                        None,
                        (by_node[item.source_node_id],),
                        item.confidence,
                    ),
                )
            keys = [node.key for node in output.nodes]
            if len(set(keys)) != len(keys):
                review = True
                continue
            ids = {key: uuid4() for key in keys}
            for node in output.nodes:
                self.repository.save_candidate_flow_node(
                    run_id,
                    CandidateDataFlowNode(
                        ids[node.key],
                        node.name,
                        None,
                        None,
                        None,
                        None,
                        (by_node[node.source_node_id],),
                        node.confidence,
                    ),
                )
            for edge in output.edges:
                if edge.source_key not in ids or edge.destination_key not in ids:
                    review = True
                    continue
                self.repository.save_candidate_flow_edge(
                    run_id,
                    CandidateDataFlowEdge(
                        uuid4(),
                        ids[edge.source_key],
                        ids[edge.destination_key],
                        None,
                        None,
                        (),
                        (by_node[edge.source_node_id],),
                        edge.confidence,
                    ),
                )
        return review

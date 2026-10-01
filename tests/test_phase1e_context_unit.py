from __future__ import annotations

from uuid import uuid4

from crossborder_compliance.application.context_services import (
    DataItemDeduplicationService, ProductContextResolutionService,
)
from crossborder_compliance.domain.context_resolution import DedupDecision


class Repo:
    def __init__(self):
        self.dedup=[]
        self.conflicts=[]
        self.product_contexts=[]
        self.scope_resolutions=[]
        self.defs={}

    def metadata_definition(self, definition_id):
        return self.defs.get(definition_id)

    def save_dedup_result(self, result):
        self.dedup.append(result)

    def save_conflict(self, conflict):
        self.conflicts.append(conflict)

    def save_product_context(self, context):
        self.product_contexts.append(context)

    def save_product_scope_resolution(self, resolution):
        self.scope_resolutions.append(resolution)


class Similarity:
    def candidate_similarity(self, *, left, right):
        return 0.95


def test_semantic_similarity_is_candidate_only_and_does_not_formal_merge():
    repo=Repo(); project=uuid4()
    left={"candidate_id":str(uuid4()),"normalized_name":"alpha","value_type":"text","unit":None}
    right={"candidate_id":str(uuid4()),"normalized_name":"beta","value_type":"text","unit":None}
    result=DataItemDeduplicationService(repo,Similarity()).compare(project,left,right,version=1)
    assert result.decision==DedupDecision.POSSIBLE_SAME
    assert result.reviewer_required is True
    assert result.semantic_candidate_score==0.95
    assert len(repo.dedup)==1
    assert not hasattr(repo,"formal_items"), "semantic suggestion must not create/merge a formal DataItem"


def test_product_selection_conflict_is_explicit_and_effective_scope_stays_empty():
    repo=Repo(); project=uuid4(); selected=uuid4(); detected=uuid4()
    repo.defs[selected]={"definition_id":str(selected),"kind":"PRODUCT","code":"fixture-a","display_name":"Fixture A"}
    repo.defs[detected]={"definition_id":str(detected),"kind":"PRODUCT","code":"fixture-b","display_name":"Fixture B"}

    resolution=ProductContextResolutionService(repo).resolve(
        project,selected_scope=(selected,),detected_scope=(detected,),
        source_trace_ids=(),version=1,
    )
    assert resolution.resolution_status=="REVIEW_REQUIRED"
    assert resolution.review_required is True
    assert resolution.effective_product_scope==()
    assert repo.conflicts and repo.conflicts[0].conflict_type=="PRODUCT_CONTEXT_CONFLICT"


def test_no_selected_product_uses_document_detected_scope_not_all_registry():
    repo=Repo(); project=uuid4(); detected=uuid4(); unrelated=uuid4()
    repo.defs[detected]={"definition_id":str(detected),"kind":"PRODUCT","code":"fixture-a","display_name":"Fixture A"}
    repo.defs[unrelated]={"definition_id":str(unrelated),"kind":"PRODUCT","code":"fixture-b","display_name":"Fixture B"}

    resolution=ProductContextResolutionService(repo).resolve(
        project,selected_scope=(),detected_scope=(detected,),version=1,
    )
    assert resolution.effective_product_scope==(detected,)
    assert unrelated not in resolution.effective_product_scope
    assert not repo.conflicts

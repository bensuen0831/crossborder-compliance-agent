from __future__ import annotations

from pathlib import Path

from crossborder_compliance.infrastructure.persistence.models import Base, ConversationThreadEntity


def test_source_of_truth_tables_are_normalized() -> None:
    tables = set(Base.metadata.tables)
    assert "classification_results" in tables
    assert "data_classifications" not in tables
    assert "workflow_stage_views" not in tables
    assert "analysis_stage_results" in tables
    assert "regulatory_structure_nodes" in tables
    assert "legal_basis_rule_hit_links" in tables
    assert "legal_basis_evidence_links" in tables
    assert "api_idempotency_records" in tables
    assert "execution_idempotency_records" in tables
    assert "checkpoints" not in tables
    assert "checkpoint_writes" not in tables
    assert "checkpoint_blobs" not in tables


def test_conversation_thread_is_not_langgraph_thread() -> None:
    assert not hasattr(ConversationThreadEntity, "thread_id")
    adapter = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "crossborder_compliance"
        / "workflows"
        / "langgraph_adapter.py"
    ).read_text(encoding="utf-8")
    assert '"thread_id": str(workflow_run_id)' in adapter

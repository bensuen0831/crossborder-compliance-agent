from pathlib import Path
from crossborder_compliance.workflows.state import SmokeGraphState
def test_state_contains_no_runtime_service_or_secret_fields():
    fields=set(SmokeGraphState.__annotations__)
    forbidden={"db_session","repository","client","secret","api_key","provider","document_bytes","knowledge_chunks"}
    assert fields.isdisjoint(forbidden)
def test_human_review_node_not_agent_registry_pattern():
    root=Path(__file__).resolve().parents[1]/"src"/"crossborder_compliance"
    assert not any("HumanReviewNode" in p.read_text(errors="ignore") for p in root.rglob("*.py"))

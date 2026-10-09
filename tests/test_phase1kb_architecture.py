from pathlib import Path

from scripts.phase1kb_architecture_check import check
from scripts.phase1kb_ownership import BASE, PATHS, overlay


def test_phase1kb_additive_architecture_and_finite_committed_ownership():
    root = Path(__file__).resolve().parents[1]
    valid, paths, source = overlay(root)
    assert valid and source and source != BASE and paths.keys() <= PATHS
    assert "src/crossborder_compliance/domain/decision_engine.py" not in paths
    assert "src/crossborder_compliance/workflows/langgraph_adapter.py" not in paths
    result = check(root)
    assert result["total"] == 27 and result["pass_"], result

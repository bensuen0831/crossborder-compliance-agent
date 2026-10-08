from pathlib import Path

from scripts.m2d_architecture_check import check
from scripts.m2d_ownership import BASE, PATHS, overlay


def test_m2d_approved_finite_owner_preserves_baseline_authorities():
    root = Path(__file__).resolve().parents[1]
    valid, paths, source = overlay(root)
    assert valid and source and source != BASE and paths.keys() <= PATHS
    assert "src/crossborder_compliance/domain/decision_engine.py" not in paths
    assert "src/crossborder_compliance/workflows/langgraph_adapter.py" not in paths


def test_m2d_additive_review_architecture():
    result = check(Path(__file__).resolve().parents[1])
    assert result["total"] == 21 and result["pass_"], result

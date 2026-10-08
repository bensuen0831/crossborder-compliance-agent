from pathlib import Path

from scripts.m2c_architecture_check import check
from scripts.m2c_ownership import BASE, PATHS, overlay


def test_c0_additive_architecture_boundaries():
    result = check(Path(__file__).resolve().parents[1])
    assert result["total"] == 15
    assert result["pass_"], result


def test_c0_owner_is_finite_committed_and_preserves_frozen_engines():
    valid, paths, source = overlay(Path(__file__).resolve().parents[1])
    from scripts.m2c_projection_ownership import PATHS as C1_PATHS

    from scripts.m2d_ownership import overlay as review_overlay
    review_valid, review_paths, _ = review_overlay(Path(__file__).resolve().parents[1])
    assert review_valid and valid and source != BASE and paths.keys() == PATHS | C1_PATHS | review_paths.keys()
    assert "src/crossborder_compliance/domain/decision_engine.py" not in paths
    assert not any(p.startswith("frontend/") for p in PATHS)

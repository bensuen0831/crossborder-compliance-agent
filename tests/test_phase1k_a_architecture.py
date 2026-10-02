import runpy
from pathlib import Path


def test_track_b_boundaries_and_all_frozen_implementation_hashes():
    root = Path(__file__).resolve().parents[1]
    result = runpy.run_path(str(root / "scripts/phase1k_a_boundary_check.py"))["check"](root)
    assert result["total"] == 20
    assert result["pass"], result["checks"]

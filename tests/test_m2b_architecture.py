"""The additive M2-B architecture check participates in mandatory pytest."""
from pathlib import Path
from scripts.m2b_architecture_check import check


def test_m2b_temporal_architecture():
    result = check(Path(__file__).resolve().parents[1])
    assert result["pass"], result["checks"]

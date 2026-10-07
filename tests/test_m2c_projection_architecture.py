from pathlib import Path
from scripts.m2c_projection_architecture import check


def test_c1_additive_projection_ownership():
    result = check(Path(__file__).resolve().parents[1])
    assert result["total"] == 15 and result["pass_"], result

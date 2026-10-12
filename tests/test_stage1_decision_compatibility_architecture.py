from pathlib import Path
from scripts.stage1_decision_compatibility_architecture import check

def test_all_additive_compatibility_architecture_invariants():
    result=check(Path(__file__).resolve().parents[1])
    assert len(result)==8 and all(result.values()),result

from pathlib import Path

from scripts.m2d_architecture_check import check
from scripts.m2d_ownership import BASE, PATHS, overlay
from scripts.m2e_r1_ownership import PATHS as RECOVERY_PATHS
from scripts.m2e_r1_ownership import overlay as recovery_overlay
from scripts.phase1l_b_ownership import overlay as runtime_overlay


def test_m2d_approved_finite_owner_preserves_baseline_authorities():
    root = Path(__file__).resolve().parents[1]
    valid, paths, source = overlay(root)
    recovery_valid, recovery_paths, recovery_source = recovery_overlay(root)
    assert valid and source and source != BASE
    assert recovery_valid and paths.keys() <= PATHS | RECOVERY_PATHS
    assert "src/crossborder_compliance/domain/decision_engine.py" not in paths
    adapter = "src/crossborder_compliance/workflows/langgraph_adapter.py"
    # M2-D never owns runtime changes. A later independently authenticated
    # recovery may forward the runtime owner's exact approved successor bytes.
    assert adapter not in PATHS
    if adapter in paths:
        runtime_valid, runtime_paths, runtime_source = runtime_overlay(root)
        assert recovery_source == source == runtime_source
        assert runtime_valid and paths[adapter] == recovery_paths[adapter] == runtime_paths[adapter]


def test_m2d_additive_review_architecture():
    result = check(Path(__file__).resolve().parents[1])
    assert result["total"] == 21 and result["pass_"], result

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
    allowed = PATHS | RECOVERY_PATHS
    if (root / "evidence/stage1-gap-kb01/approved_owner_overlay.json").exists():
        from scripts.kb01_ownership import authenticated_paths

        assert source == recovery_source
        allowed |= authenticated_paths(root, source)
    assert recovery_valid and paths.keys() <= allowed
    engine = "src/crossborder_compliance/domain/decision_engine.py"
    if engine in paths:
        import json, subprocess
        from scripts.stage1_e2e_ownership import BASE as approved_base, legal_bodies_preserved
        root=Path(__file__).resolve().parents[1]
        record=json.loads((root/"evidence/stage1-full-e2e/r2/approved_owner_overlay.json").read_text())
        assert paths[engine]==record['paths'][engine]
        assert legal_bodies_preserved(subprocess.check_output(['git','show',approved_base+':'+engine],cwd=root),(root/engine).read_bytes())
    else:
        assert engine not in paths
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

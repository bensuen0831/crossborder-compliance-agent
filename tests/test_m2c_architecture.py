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
    engine = "src/crossborder_compliance/domain/decision_engine.py"
    if engine in paths:
        # Explicit0020 exception: authenticate the finite approval and prove
        # the original legal bodies, rather than permit arbitrary owner edits.
        import json, subprocess
        from scripts.stage1_e2e_ownership import BASE as approved_base, legal_bodies_preserved
        root=Path(__file__).resolve().parents[1]
        record=json.loads((root/"evidence/stage1-full-e2e/r2/approved_owner_overlay.json").read_text())
        assert paths[engine]==record['paths'][engine]
        assert legal_bodies_preserved(subprocess.check_output(['git','show',approved_base+':'+engine],cwd=root),(root/engine).read_bytes())
    else:
        assert engine not in paths
    assert not any(p.startswith("frontend/") for p in PATHS)

from pathlib import Path

from scripts.phase1kb_architecture_check import check
from scripts.phase1kb_ownership import BASE, PATHS, overlay


def test_phase1kb_additive_architecture_and_finite_committed_ownership():
    root = Path(__file__).resolve().parents[1]
    valid, paths, source = overlay(root)
    allowed = PATHS
    if (root / "evidence/stage1-gap-kb01/approved_owner_overlay.json").exists():
        from scripts.kb01_ownership import authenticated_paths

        allowed |= authenticated_paths(root, source)
    assert valid and source and source != BASE and paths.keys() <= allowed
    engine = "src/crossborder_compliance/domain/decision_engine.py"
    if engine in paths:
        import json, subprocess
        from scripts.stage1_e2e_ownership import BASE as approved_base, legal_bodies_preserved
        record = json.loads((root / "evidence/stage1-full-e2e/r2/approved_owner_overlay.json").read_text())
        assert paths[engine] == record["paths"][engine]
        assert legal_bodies_preserved(subprocess.check_output(["git", "show", approved_base + ":" + engine], cwd=root), (root / engine).read_bytes())
    else:
        assert engine not in paths
    assert "src/crossborder_compliance/workflows/langgraph_adapter.py" not in paths
    result = check(root)
    assert result["total"] == 27 and result["pass_"], result

"""Recovery checks detect the explicit jurisdiction and pinned-rule regressions."""

import shutil
from pathlib import Path

from scripts.m2e_r1_architecture_check import check
from scripts.m2e_r1_ownership import BASE, PATHS, R1_PATHS, overlay

ROOT = Path(__file__).resolve().parents[1]


def test_recovery_architecture_checks():
    result = check(ROOT)
    assert result["total"] == 11
    assert result["pass_"], result


def test_architecture_rejects_cross_jurisdiction_applicability(tmp_path):
    for folder in ("src", "alembic"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    file = tmp_path / "src/crossborder_compliance/application/workflow_formal.py"
    file.write_text(
        file.read_text().replace("result.jurisdiction_id == binding.jurisdiction_id", "True")
    )
    result = check(tmp_path)
    assert not result["pass_"]
    assert not result["checks"]["applicability_consumes_same_jurisdiction_classification"]


def test_recovery_is_exact_committed_finite_successor_owner():
    valid, paths, source = overlay(ROOT)
    assert valid and source and source != BASE
    allowed = PATHS
    if (ROOT / "evidence/stage1-gap-kb01/approved_owner_overlay.json").exists():
        from scripts.kb01_ownership import authenticated_paths

        allowed |= authenticated_paths(ROOT, source)
    assert paths.keys() == allowed
    assert not any(p.startswith("frontend/") for p in R1_PATHS)
    engine = "src/crossborder_compliance/domain/decision_engine.py"
    if engine in paths:
        # Only the approved compatibility successor can extend this owner.
        import json, subprocess
        from scripts.stage1_e2e_ownership import BASE as approved_base, legal_bodies_preserved
        record = json.loads((ROOT / "evidence/stage1-full-e2e/r2/approved_owner_overlay.json").read_text())
        assert paths[engine] == record["paths"][engine]
        assert legal_bodies_preserved(subprocess.check_output(["git", "show", approved_base + ":" + engine], cwd=ROOT), (ROOT / engine).read_bytes())
    else:
        assert engine not in paths
    assert "src/crossborder_compliance/infrastructure/persistence/rule_governance.py" not in paths


def test_batched_git_proof_still_rejects_live_frozen_engine_tampering(monkeypatch):
    protected = ROOT / "src/crossborder_compliance/domain/decision_engine.py"
    original = Path.read_bytes
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda path: b"unauthorized change" if path == protected else original(path),
    )
    assert not overlay(ROOT)[0]

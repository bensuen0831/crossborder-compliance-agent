"""Recovery checks detect the explicit jurisdiction and pinned-rule regressions."""

import shutil
from pathlib import Path

from scripts.m2e_r1_architecture_check import check
from scripts.m2e_r1_ownership import BASE, PATHS, overlay

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
    assert paths.keys() == PATHS
    assert not any(p.startswith("frontend/") for p in paths)
    assert "src/crossborder_compliance/domain/decision_engine.py" not in paths
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

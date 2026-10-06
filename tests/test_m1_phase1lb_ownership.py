"""Original owner boundaries survive approved later owners, never tampering."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from scripts import phase1l_b_ownership as lb
from scripts.m1_phase1lb_ownership import verify

ROOT = Path(__file__).resolve().parents[1]


def test_approved_m1_descendant_and_finite_integration_provenance():
    assert lb.owner_provenance(ROOT)
    assert lb.overlay(ROOT)[0]
    assert verify(ROOT)["pass"]


@pytest.mark.parametrize(
    "path",
    [
        "frontend/src/App.tsx",
        "src/crossborder_compliance/domain/decision_engine.py",
        "alembic/versions/0011.py",
        "ARCHITECTURE_RULES.md",
    ],
)
def test_original_lb_source_cannot_modify_forbidden_scope(monkeypatch, path):
    original = lb.subprocess.check_output

    def git(cmd, **kwargs):
        if cmd[1] == "diff" and lb.VERIFIED_SOURCE in cmd:
            return path.encode()
        return original(cmd, **kwargs)

    monkeypatch.setattr(lb.subprocess, "check_output", git)
    assert not lb.owner_provenance(ROOT)


def test_wrong_reviewed_source():
    assert not lb.owner_provenance(ROOT, source=lb.BASE)


def test_unrelated_source_ancestry(monkeypatch):
    monkeypatch.setattr(lb.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    assert not lb.owner_provenance(ROOT)


def test_arbitrary_integration_path_rejected(monkeypatch):
    import scripts.m1_phase1lb_ownership as integration

    original = integration.subprocess.check_output

    def git(cmd, **kwargs):
        if cmd[1:4] == ["diff", "--name-only", integration.SYNC]:
            return b"src/crossborder_compliance/domain/decision_engine.py\n"
        return original(cmd, **kwargs)

    monkeypatch.setattr(integration.subprocess, "check_output", git)
    assert not verify(ROOT)["pass"]

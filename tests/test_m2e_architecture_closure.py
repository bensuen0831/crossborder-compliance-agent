"""Finite resume ownership and gateway boundaries reject owner/contract tampering."""

import shutil
from pathlib import Path

from scripts.m2e_architecture_check import check
from scripts.m2e_r1_ownership import overlay

ROOT = Path(__file__).resolve().parents[1]


def test_additive_gateway_architecture():
    result = check(ROOT)
    assert result["total"] == 27 and result["passed"] == 27, result


def test_gateway_cannot_import_formal_engine(tmp_path):
    for folder in ("src", "alembic", "frontend/src/features/integrations", "sdk"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    path = tmp_path / "src/crossborder_compliance/application/external_channel.py"
    path.write_text(
        path.read_text() + "\nfrom crossborder_compliance.domain import decision_engine\n"
    )
    result = check(tmp_path)
    assert not result["pass_"] and not result["checks"]["external_has_no_legal_owner"]


def test_finite_resume_proof_does_not_authorize_r1_engine_change(monkeypatch):
    path = (
        ROOT / "src/crossborder_compliance/infrastructure/persistence/classification_repository.py"
    )
    original = Path.read_bytes
    monkeypatch.setattr(
        Path, "read_bytes", lambda p: b"altered owner" if p == path else original(p)
    )
    assert not overlay(ROOT)[0]

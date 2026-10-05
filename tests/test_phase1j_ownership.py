"""Owner approvals use finite exact Git blobs, never current acceptance hashes."""

import json
from pathlib import Path

import pytest

from scripts.phase1j_ownership import overlay


def test_reviewed_owner_record_and_untouched_historical_migrations():
    root = Path(__file__).resolve().parents[1]
    valid, paths, source = overlay(root)
    assert valid and paths and source


@pytest.mark.parametrize(
    "change",
    [
        "hash",
        "sdk",
        "workflow",
        "historical_migration",
        "future_revision",
        "unrelated_source",
        "wrong_base",
    ],
)
def test_owner_overlay_rejects_unreviewed_changes(monkeypatch, change):
    root = Path(__file__).resolve().parents[1]
    record = root / "evidence/phase1j/approved_owner_overlay.json"
    data = json.loads(record.read_text())
    if change == "hash":
        data["paths"]["alembic/env.py"] = "0" * 64
    elif change == "unrelated_source":
        data["source_sha"] = data["round2_sha"]
    elif change == "wrong_base":
        data["base_sha"] = data["round2_sha"]
    else:
        path = {
            "sdk": "src/crossborder_compliance/domain/llm_gateway.py",
            "workflow": "src/crossborder_compliance/workflows/langgraph_adapter.py",
            "historical_migration": "alembic/versions/0009_phase1i_applicability.py",
            "future_revision": "alembic/versions/0011_arbitrary.py",
        }[change]
        data["paths"][path] = "0" * 64
    original = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda p, *a, **kw: json.dumps(data) if p == record else original(p, *a, **kw),
    )
    assert not overlay(root)[0]

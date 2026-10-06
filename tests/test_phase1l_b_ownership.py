"""Runtime owner transfer requires reviewed immutable Git objects."""

import json
import runpy
from pathlib import Path

import pytest

overlay = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/phase1l_b_ownership.py")
)["overlay"]


def test_approved_runtime_owner_transfer_and_frozen_domain_migrations():
    valid, paths, source = overlay(Path(__file__).resolve().parents[1])
    assert valid and len(paths) == 1 and source


@pytest.mark.parametrize(
    "change", ["hash", "frontend", "domain", "migration", "wrong_base", "unrelated_source"]
)
def test_transfer_rejects_unapproved_paths_and_sources(monkeypatch, change):
    root = Path(__file__).resolve().parents[1]
    record = root / "evidence/phase1l_b/approved_owner_overlay.json"
    data = json.loads(record.read_text())
    if change == "hash":
        data["paths"]["src/crossborder_compliance/workflows/langgraph_adapter.py"] = "0" * 64
    elif change == "wrong_base":
        data["base_sha"] = "594be84cfc471af4c12f28600b22cffb66f830f7"
    elif change == "unrelated_source":
        data["source_sha"] = data["base_sha"]
    else:
        data["paths"][
            {
                "frontend": "frontend/src/main.tsx",
                "domain": "src/crossborder_compliance/domain/decision_engine.py",
                "migration": "alembic/versions/0011.py",
            }[change]
        ] = "0" * 64
    original = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda p, *a, **kw: json.dumps(data) if p == record else original(p, *a, **kw),
    )
    assert not overlay(root)[0]

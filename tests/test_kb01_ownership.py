"""Committed-blob scope proof rejects tampering, including permitted paths."""

import json
import subprocess
from pathlib import Path

import pytest

from scripts.kb01_ownership import (
    FIFTH_RECORD,
    FOURTH_RECORD,
    RECORD,
    SECOND_RECORD,
    SUCCESSOR_RECORD,
    THIRD_RECORD,
    authenticated_paths,
    overlay,
)

ROOT = Path(__file__).resolve().parents[1]


def test_kb01_ownership_authenticates_committed_source():
    valid, paths, source = overlay(ROOT)
    assert valid and source and len(paths) > 0


@pytest.mark.parametrize(
    "path",
    [
        "alembic/versions/0020_stage1_formal_decision_engine_compatibility.py",
        "src/crossborder_compliance/domain/decision_engine.py",
        "evidence/stage1-full-e2e/r3/approved_owner_overlay.json",
        "src/crossborder_compliance/domain/knowledge_management.py",
        "src/crossborder_compliance/application/unapproved_kb_shortcut.py",
        RECORD,
        SECOND_RECORD,
        THIRD_RECORD,
        "alembic/versions/0022_kb01_binary_transport.py",
        FOURTH_RECORD,
        FIFTH_RECORD,
        "alembic/versions/0023_kb01_evidence_source_reference.py",
        "alembic/versions/0021_kb01_taxonomy_operations.py",
        "src/crossborder_compliance/infrastructure/knowledge_import_worker.py",
        "src/crossborder_compliance/infrastructure/persistence/regulatory_acceptance_governance.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_translation_alignment.py",
    ],
)
def test_kb01_ownership_rejects_uncommitted_tampering(tmp_path, path):
    copy = tmp_path / "repo"
    subprocess.run(["git", "clone", "--no-hardlinks", "--quiet", str(ROOT), str(copy)], check=True)
    assert overlay(copy)[0]
    target = copy / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("ab") as output:
        output.write(b"\n# unauthorized mutation\n")
    assert not overlay(copy)[0]


def test_kb01_ownership_rejects_live_hash_self_certification(tmp_path):
    copy = tmp_path / "repo"
    subprocess.run(["git", "clone", "--no-hardlinks", "--quiet", str(ROOT), str(copy)], check=True)
    data = json.loads((copy / SUCCESSOR_RECORD).read_text())
    data["paths"]["src/crossborder_compliance/domain/knowledge_management.py"] = "0" * 64
    (copy / SUCCESSOR_RECORD).write_text(json.dumps(data))
    assert not overlay(copy)[0]


def test_kb01_successor_bounds_require_matching_source():
    valid, paths, source = overlay(ROOT)
    assert valid and authenticated_paths(ROOT, source) == paths.keys()
    with pytest.raises(ValueError, match="does not authenticate"):
        authenticated_paths(ROOT, "0" * 40)

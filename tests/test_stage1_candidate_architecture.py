"""Additive owner checks detect hidden confirm extraction and consent bypass."""

import shutil
from pathlib import Path

from scripts.stage1_candidate_architecture import check

ROOT = Path(__file__).resolve().parents[1]


def test_additive_candidate_owner_architecture():
    checks = check(ROOT)
    assert len(checks) == 24 and all(checks.values()), checks


def test_architecture_detects_hidden_confirm_extraction(tmp_path):
    for directory in ("src", "alembic"):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    path = tmp_path / "src/crossborder_compliance/infrastructure/intake_composition.py"
    source = path.read_text().replace(
        "    project_id = intake.project_id",
        "    prepare_document_candidates()\n    project_id = intake.project_id",
        1,
    )
    path.write_text(source)
    checks = check(tmp_path)
    assert not checks["confirm_does_not_generate_candidates"]
    assert not checks["confirm_does_not_call_document_llm"]

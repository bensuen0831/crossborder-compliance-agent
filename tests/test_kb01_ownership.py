"""Committed-blob scope proof rejects tampering, including permitted paths."""

import json
import subprocess
from pathlib import Path

import pytest

from scripts.kb01_ownership import (
    EIGHTEENTH_RECORD,
    EIGHTH_RECORD,
    ELEVENTH_RECORD,
    FIFTEENTH_RECORD,
    FIFTH_RECORD,
    FOURTEENTH_RECORD,
    FOURTH_RECORD,
    NINETEENTH_RECORD,
    NINTH_RECORD,
    RECORD,
    SECOND_RECORD,
    SEVENTEENTH_RECORD,
    SEVENTH_RECORD,
    SIXTEENTH_RECORD,
    SIXTH_RECORD,
    SUCCESSOR_RECORD,
    TENTH_RECORD,
    THIRD_RECORD,
    THIRTEENTH_RECORD,
    TWELFTH_RECORD,
    TWENTIETH_RECORD,
    authenticated_dependency_successor,
    authenticated_migration_successor,
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
        NINETEENTH_RECORD,
        TWENTIETH_RECORD,
        SECOND_RECORD,
        THIRD_RECORD,
        THIRTEENTH_RECORD,
        TWELFTH_RECORD,
        THIRTEENTH_RECORD,
        "alembic/versions/0022_kb01_binary_transport.py",
        FOURTEENTH_RECORD,
        FIFTEENTH_RECORD,
        SIXTEENTH_RECORD,
        SEVENTEENTH_RECORD,
        EIGHTEENTH_RECORD,
        FOURTH_RECORD,
        NINTH_RECORD,
        FIFTH_RECORD,
        SIXTH_RECORD,
        SEVENTH_RECORD,
        EIGHTH_RECORD,
        ELEVENTH_RECORD,
        NINTH_RECORD,
        TENTH_RECORD,
        TWELFTH_RECORD,
        THIRTEENTH_RECORD,
        "frontend/e2e/kb01-safe-evidence.ts",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_manifest_models.py",
        "scripts/stage1_alpha_integrity.py",
        ".github/workflows/kb01-knowledge-management.yml",
        "frontend/package-lock.json",
        "frontend/package.json",
        "scripts/kb01/Containerfile",
        "scripts/kb01/toolchain_provenance.py",
        "scripts/kb01/rc1.py",
        "frontend/scripts/m1/boundary_check.py",
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


def test_kb01_dependency_successor_preserves_exact_m1_package_contract():
    assert authenticated_dependency_successor(ROOT, "f1353372a1d8894535dc71765e3cd62597619fd5")
    assert not authenticated_dependency_successor(ROOT, "not-an-approved-baseline")


def test_m1_boundary_retains_every_original_check_with_authenticated_dependency():
    import ast

    legacy = subprocess.check_output(
        [
            "git",
            "show",
            "5b1aaf5df05de458a65ead497536b323ecb16ce9:frontend/scripts/m1/boundary_check.py",
        ],
        cwd=ROOT,
        text=True,
    )
    original_keys = next(
        {key.value for key in node.value.keys}
        for node in ast.parse(legacy).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "checks" for target in node.targets)
    )
    result = json.loads(
        subprocess.check_output(
            [
                "python",
                "frontend/scripts/m1/boundary_check.py",
            ],
            cwd=ROOT,
            text=True,
        )
    )
    assert result["status"] == "PASS"
    assert set(result["checks"]) == original_keys
    assert all(result["checks"].values())


def test_kb01_schema_successor_authenticates_complete_committed_migration_tree():
    assert authenticated_migration_successor(ROOT, "0024_kb01_import_manifest_records")


@pytest.mark.parametrize(
    "head", ["head", "0020_stage1_formal_decision_engine_compatibility", "0025_unapproved"]
)
def test_kb01_schema_successor_rejects_unapproved_or_alias_heads(head):
    assert not authenticated_migration_successor(ROOT, head)

"""Finite KB01 V2 scope successor, authenticated from committed Git blobs.

No historical manifest or legal-engine algorithm is replaced. Tests and source
outside the explicit management adapter paths remain byte-preserved.
"""

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

BASE = "060cbb5a20a9f8f70fa88dbefb8b5feb404c460d"
RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay.json"
SUCCESSOR_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v2.json"
FIRST_SEAL = "a95d5f05f46566d7e58417a8c9cb2214c6d028f0"
FIRST_SOURCE = "6f0f448fbe5d72494d2756bca30a3f74437e1f63"
PREVIOUS = "evidence/stage1-full-e2e/r3/approved_owner_overlay.json"
PATHS = frozenset(
    (
        "scripts/stage1_business_architecture.py",
        "scripts/m2a_ownership.py",
        "ARCHITECTURE_RULES.md",
        "scripts/kb01_architecture_check.py",
        "scripts/architecture_rule_check.py",
        "tests/test_kb01_architecture.py",
        "tests/test_m2d_architecture.py",
        "tests/test_m2e_r1_architecture.py",
        "tests/test_phase1kb_architecture.py",
        "alembic/env.py",
        "alembic/versions/0021_kb01_taxonomy_operations.py",
        "scripts/kb01_ownership.py",
        "scripts/stage1_e2e_r3_ownership.py",
        "src/crossborder_compliance/application/knowledge_document_management.py",
        "src/crossborder_compliance/application/knowledge_manifest.py",
        "src/crossborder_compliance/application/knowledge_taxonomy.py",
        "src/crossborder_compliance/domain/knowledge_management.py",
        "src/crossborder_compliance/infrastructure/knowledge_manifest_parser.py",
        "src/crossborder_compliance/infrastructure/persistence/compliance_profile_governance.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_document_management.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_management_models.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_models.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_taxonomy.py",
        "src/crossborder_compliance/infrastructure/persistence/metadata_models.py",
        "src/crossborder_compliance/infrastructure/persistence/metadata_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/taxonomy_governance.py",
        "src/crossborder_compliance/infrastructure/registry_catalog.py",
        "src/crossborder_compliance/interfaces/api/knowledge_management_schemas.py",
        "src/crossborder_compliance/interfaces/api/main.py",
        "src/crossborder_compliance/interfaces/api/routes/admin_metadata.py",
        "src/crossborder_compliance/interfaces/api/routes/knowledge_document_management.py",
        "src/crossborder_compliance/interfaces/api/routes/knowledge_management.py",
        "src/crossborder_compliance/interfaces/api/routes/metadata.py",
        "tests/test_kb01_document_management_postgres.py",
        "tests/test_kb01_ownership.py",
        "tests/test_kb01_taxonomy_migrations.py",
        "tests/test_kb01_taxonomy_postgres.py",
        "tests/test_knowledge_manifest.py",
        "tests/test_stage1_candidate_governance_migrations.py",
        "tests/test_stage1_decision_compatibility_migrations.py",
    )
)


def overlay(root):
    root = Path(root).resolve()

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "core.quotepath=false", *args], cwd=root, stderr=subprocess.DEVNULL
        )

    def ancestor(a, b):
        return (
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", a, b], cwd=root, stderr=subprocess.DEVNULL
            ).returncode
            == 0
        )

    def blobs(source, paths):
        with tarfile.open(
            fileobj=io.BytesIO(git("archive", source, "--", *sorted(paths)))
        ) as archive:
            return {
                item.name: archive.extractfile(item).read() for item in archive if item.isfile()
            }

    try:
        baseline_paths = git("ls-tree", "-r", "--name-only", BASE).decode().splitlines()
        originals = blobs(BASE, baseline_paths)
        previous = json.loads(originals[PREVIOUS])
        if (root / PREVIOUS).read_bytes() != originals[PREVIOUS] or not ancestor(
            previous["source_sha"], BASE
        ):
            return False, {}, None
        historical = blobs(previous["source_sha"], previous["paths"])
        if any(
            hashlib.sha256(historical[path]).hexdigest() != digest
            for path, digest in previous["paths"].items()
        ):
            return False, {}, None
        first_bytes = git("show", FIRST_SEAL + ":" + RECORD)
        if (root / RECORD).read_bytes() != first_bytes or not ancestor(FIRST_SEAL, "HEAD"):
            return False, {}, None
        first = json.loads(first_bytes)
        if first["source_sha"] != FIRST_SOURCE or first["base_sha"] != BASE:
            return False, {}, None
        first_blobs = blobs(FIRST_SOURCE, first["paths"])
        if any(
            hashlib.sha256(first_blobs[path]).hexdigest() != digest
            for path, digest in first["paths"].items()
        ):
            return False, {}, None
        record = json.loads((root / SUCCESSOR_RECORD).read_text())
        expected = set(previous["paths"]) | PATHS
        source = record["source_sha"]
        if (
            record["base_sha"] != BASE
            or record["scope"] != "STAGE1-GAP-KB01-MASTER_V2.0"
            or set(record["paths"]) != expected
            or not ancestor(BASE, source)
            or not ancestor(FIRST_SEAL, source)
            or not ancestor(source, "HEAD")
        ):
            return False, {}, None
        committed = blobs(source, expected)
        if any(
            hashlib.sha256(committed[path]).hexdigest() != digest
            or (root / path).read_bytes() != committed[path]
            for path, digest in record["paths"].items()
        ):
            return False, {}, None
        if any(
            (root / path).read_bytes() != originals[path]
            for path in baseline_paths
            if path not in PATHS
        ):
            return False, {}, None
        changes = (
            set(git("diff", "--name-only", BASE, source).decode().splitlines())
            | set(git("diff", "--name-only", BASE).decode().splitlines())
            | set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
        )
        if any(
            path not in PATHS
            and not path.startswith(("docs/stage1-gap-kb01/", "evidence/stage1-gap-kb01/"))
            for path in changes
        ):
            return False, {}, None
        # No path exception includes historical migrations or legal engines.
        if any(
            path.startswith("alembic/versions/")
            and path.split("/")[-1][:4].isdigit()
            and int(path.split("/")[-1][:4]) <= 20
            for path in PATHS
        ):
            return False, {}, None
        return True, record["paths"], source
    except (OSError, KeyError, ValueError, TypeError, subprocess.CalledProcessError):
        return False, {}, None


def authenticated_paths(root, source):
    """Extend a prior owner's finite bounds only with this exact proven successor."""
    valid, paths, successor_source = overlay(root)
    if not valid or successor_source != source:
        raise ValueError("KB01 successor source does not authenticate")
    return frozenset(paths)

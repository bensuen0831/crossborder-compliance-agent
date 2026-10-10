"""Finite authorized M2-E WIP / R1 owning recovery, authenticated Git source bytes.

This terminal successor overlay reuses the historical owner-proof chain. It
permits only enumerated files and committed hashes, never live-hash approval.
It is not an M2-E closure/production readiness decision.
"""

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

BASE = "0f5a40c5ca3a8771624fb38e9380856d79e67342"
PATHS = frozenset(
    [
        "alembic/env.py",
        "alembic/versions/0017_m2e_external_agent_api.py",
        "alembic/versions/0018_phase1h_multijurisdiction_classification_identity.py",
        "scripts/m2d_ownership.py",
        "scripts/m2e_r1_architecture_check.py",
        "scripts/m2e_r1_ownership.py",
        "scripts/phase1kb_ownership.py",
        "src/crossborder_compliance/application/classification_services.py",
        "src/crossborder_compliance/application/external_channel.py",
        "src/crossborder_compliance/application/integrations.py",
        "src/crossborder_compliance/application/workflow_formal.py",
        "src/crossborder_compliance/domain/classification.py",
        "src/crossborder_compliance/domain/integrations.py",
        "src/crossborder_compliance/domain/regulation_applicability.py",
        "src/crossborder_compliance/domain/rules.py",
        "src/crossborder_compliance/infrastructure/external_composition.py",
        "src/crossborder_compliance/infrastructure/intake_composition.py",
        "src/crossborder_compliance/infrastructure/integration_worker.py",
        "src/crossborder_compliance/infrastructure/persistence/classification_governance.py",
        "src/crossborder_compliance/infrastructure/persistence/classification_repository.py",
        "src/crossborder_compliance/infrastructure/persistence/country_compliance_repository.py",
        "src/crossborder_compliance/infrastructure/persistence/integration_models.py",
        "src/crossborder_compliance/infrastructure/persistence/integrations.py",
        "src/crossborder_compliance/infrastructure/persistence/special_admin_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/webhooks.py",
        "src/crossborder_compliance/infrastructure/webhook_http.py",
        "src/crossborder_compliance/interfaces/api/external_schemas.py",
        "src/crossborder_compliance/interfaces/api/main.py",
        "src/crossborder_compliance/interfaces/api/routes/classification.py",
        "src/crossborder_compliance/interfaces/api/routes/external.py",
        "src/crossborder_compliance/interfaces/api/routes/integrations.py",
        "src/crossborder_compliance/interfaces/api/workflow_app.py",
        "src/crossborder_compliance/workflows/langgraph_adapter.py",
        "tests/m2e_fixtures.py",
        "tests/test_m2e_http.py",
        "tests/test_m2e_identity_postgres.py",
        "tests/test_m2e_r11_migrations.py",
        "tests/test_m2e_r1_architecture.py",
        "tests/test_m2e_r1_classification_postgres.py",
        "tests/test_m2e_r1_isolation.py",
        "tests/test_m2e_vertical_postgres.py",
        "tests/test_m2e_webhooks_postgres.py",
    ]
)
PATHS = PATHS | {
    "scripts/m2a_ownership.py",
    "scripts/phase1l_b_ownership.py",
    "tests/test_m2b_snapshot_contract_probe.py",
    "tests/test_m2d_architecture.py",
    "tests/test_phase1kb_migrations.py",
}


R1_PATHS = PATHS
from scripts.m2e_resume_ownership import RESUME_PATHS
PATHS = PATHS | RESUME_PATHS


def overlay(root):
    root = Path(root)
    if (root / "evidence/m2e/resume_approved_owner_overlay.json").exists():
        from scripts.m2e_resume_ownership import overlay as resume_overlay
        return resume_overlay(root, R1_PATHS)
    record = root / "evidence/m2e/r1_approved_owner_overlay.json"
    if not record.exists():
        return True, {}, None
    try:
        data = json.loads(record.read_text())
        source = data["source_sha"]

        def git(*args):
            return subprocess.check_output(
                ["git", "-c", "core.quotepath=false", *args], cwd=root, stderr=subprocess.DEVNULL
            )

        def ancestor(a, b):
            return (
                subprocess.run(
                    ["git", "merge-base", "--is-ancestor", a, b],
                    cwd=root,
                    stderr=subprocess.DEVNULL,
                ).returncode
                == 0
            )

        def blobs(sha, paths):
            # Batch immutable Git-object reads only. Current files and proof
            # records are still rechecked on every invocation; no cached
            # authorization/validity can hide a later modification.
            archive = git("archive", "--format=tar", sha, "--", *paths)
            with tarfile.open(fileobj=io.BytesIO(archive)) as files:
                return {
                    entry.name: files.extractfile(entry).read() for entry in files if entry.isfile()
                }

        valid = (
            data["base_sha"] == BASE
            and source != BASE
            and ancestor(BASE, source)
            and ancestor(source, "HEAD")
        )
        valid = valid and set(data["paths"]) == R1_PATHS
        committed = blobs(source, sorted(R1_PATHS))
        valid = valid and all(
            hashlib.sha256(committed[p]).hexdigest() == h
            and (root / p).read_bytes() == committed[p]
            for p, h in data["paths"].items()
        )
        baseline = (
            git(
                "ls-tree",
                "-r",
                "--name-only",
                BASE,
                "--",
                "src",
                "alembic/versions",
                "frontend",
                "evidence",
            )
            .decode()
            .splitlines()
        )
        baseline += ["ARCHITECTURE_RULES.md", "pyproject.toml"]
        original = blobs(BASE, baseline)
        valid = valid and all(
            (root / p).read_bytes() == original[p] for p in baseline if p not in R1_PATHS
        )
        delta = set(git("diff", "--name-only", BASE, source).decode().splitlines())
        valid = valid and all(
            p in R1_PATHS or p.startswith(("docs/m2e/", "evidence/m2e/")) for p in delta
        )
        return valid, data["paths"], source
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        return False, {}, None

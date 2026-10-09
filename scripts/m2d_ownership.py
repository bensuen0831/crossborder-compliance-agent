"""Finite M2-D owner transfer anchored to the verified M2-C main commit."""

import hashlib
import json
import subprocess
from pathlib import Path

from scripts.phase1kb_ownership import PATHS as LLM_PATHS

BASE = "0dc005e583465a4604a5d40a369cb5fc2f0ccbef"
MIGRATION = "alembic/versions/0015_m2d_review_governance.py"
# Maintained explicitly before certification; never inferred from live changes.
PATHS = frozenset(
    {
        MIGRATION,
        "alembic/env.py",
        "scripts/m2d_ownership.py",
        "scripts/m2d_architecture_check.py",
        "scripts/m2c_projection_ownership.py",
        "scripts/m2a_ownership.py",
        "scripts/m2b_ownership.py",
        "src/crossborder_compliance/application/review_services.py",
        "src/crossborder_compliance/application/context_ports.py",
        "src/crossborder_compliance/application/context_services.py",
        "src/crossborder_compliance/domain/review_governance.py",
        "src/crossborder_compliance/infrastructure/intake_composition.py",
        "src/crossborder_compliance/infrastructure/persistence/context_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/document_snapshot_inputs.py",
        "src/crossborder_compliance/infrastructure/persistence/models.py",
        "src/crossborder_compliance/infrastructure/persistence/postgres_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/project_intake.py",
        "src/crossborder_compliance/infrastructure/persistence/repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/review_governance.py",
        "src/crossborder_compliance/infrastructure/persistence/review_models.py",
        "src/crossborder_compliance/infrastructure/workflow_formal_composition.py",
        "src/crossborder_compliance/interfaces/api/routes/reviews.py",
        "src/crossborder_compliance/interfaces/api/routes/intake.py",
        "src/crossborder_compliance/interfaces/api/workflow_app.py",
        "src/crossborder_compliance/workflows/canonical.py",
        "tests/test_m2c_architecture.py",
        "tests/test_m2c_migrations.py",
        "tests/test_m2d_review_contracts.py",
        "tests/test_m2d_review_postgres.py",
        "tests/test_m2d_correction_postgres.py",
        "tests/test_m2d_api_postgres.py",
        "tests/test_m2d_migrations.py",
        "tests/test_m2d_architecture.py",
        "tests/test_m2d_formal_review_postgres.py",
        "frontend/src/App.tsx",
        "frontend/src/api/client.ts",
        "frontend/src/api/m2d-generated.ts",
        "frontend/src/api/m2d-schemas.json",
        "frontend/src/features/reviews/api.ts",
        "frontend/src/features/reviews/ReviewCenter.tsx",
        "frontend/src/features/reviews/reviews.test.tsx",
        "frontend/src/features/results/Stage1Workspace.tsx",
        "frontend/src/locales/en-US.json",
        "frontend/src/locales/zh-CN.json",
        "frontend/src/locales/zh-HK.json",
        "frontend/scripts/m2d/export_contracts.py",
        "frontend/scripts/m2d/uat.py",
        "frontend/scripts/m2a/uat.py",
        "frontend/e2e/m2d.spec.ts",
        "frontend/vite.config.ts",
        ".github/workflows/m2d-human-review.yml",
        ".github/workflows/phase1a-runtime-smoke.yml",
    }
)

# Explicit additive owner transfer; the successor overlay validates its own committed hashes.

PATHS = PATHS | LLM_PATHS


def overlay(root):
    root = Path(root)
    record = root / "evidence/m2d/approved_owner_overlay.json"
    if not record.exists():
        return True, {}, None
    try:
        data = json.loads(record.read_text())
        source = data["source_sha"]
        from scripts.phase1kb_ownership import overlay as llm_overlay

        llm_valid, llm_paths, llm_source = llm_overlay(root)
        from scripts.m2e_r1_ownership import overlay as recovery_overlay

        recovery_valid, recovery_paths, _ = recovery_overlay(root)
        llm_valid = llm_valid and recovery_valid
        llm_paths = {**llm_paths, **recovery_paths}

        def git(*args):
            return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL)

        def ancestor(a, b):
            return (
                subprocess.run(
                    ["git", "merge-base", "--is-ancestor", a, b],
                    cwd=root,
                    stderr=subprocess.DEVNULL,
                ).returncode
                == 0
            )

        valid = llm_valid and (
            data["base_sha"] == BASE
            and source != BASE
            and ancestor(BASE, source)
            and ancestor(source, "HEAD")
            and set(data["paths"]) <= PATHS
            and "scripts/m2d_ownership.py" in data["paths"]
        )
        valid = valid and all(
            hashlib.sha256(git("show", source + ":" + p)).hexdigest() == h
            and ((root / p).read_bytes() == git("show", source + ":" + p) or p in llm_paths)
            for p, h in data["paths"].items()
        )
        frozen = (
            git(
                "ls-tree",
                "-r",
                "--name-only",
                BASE,
                "--",
                "alembic/versions",
                "evidence",
                "src/crossborder_compliance/domain",
                "src/crossborder_compliance/workflows/langgraph_adapter.py",
            )
            .decode()
            .splitlines()
        )
        frozen += [
            "ARCHITECTURE_RULES.md",
            "pyproject.toml",
            "frontend/package.json",
            "frontend/package-lock.json",
            "src/crossborder_compliance/domain/decision_engine.py",
            "src/crossborder_compliance/domain/formal_result_engine.py",
        ]
        valid = valid and all(
            (root / p).read_bytes() == git("show", BASE + ":" + p)
            for p in frozen
            if p not in llm_paths
        )
        delta = set(git("diff", "--name-only", BASE, source).decode().splitlines())
        valid = valid and delta <= set(data["paths"]) | {
            p for p in delta if p.startswith(("docs/m2d/", "evidence/m2d/"))
        }
        return valid, {**data["paths"], **llm_paths}, llm_source or source
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError):
        return False, {}, None

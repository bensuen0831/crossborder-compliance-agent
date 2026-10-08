"""Finite C1 ownership transfer from the measured C0 PASS checkpoint."""

import hashlib
import json
import subprocess
from pathlib import Path

BASE = "ee9bf85503b618f0f26f782446f9a1365f593992"
PATHS = frozenset(
    {
        ".github/workflows/m2c-stage1-results.yml",
        "frontend/e2e/m2c.spec.ts",
        "frontend/e2e/fixtures/m2c-intake.docx",
        "frontend/scripts/m1/export_contracts.py",
        "frontend/scripts/m1/uat.py",
        "frontend/scripts/m2a/uat.py",
        "frontend/scripts/m2c/export_contracts.py",
        "frontend/src/App.tsx",
        "frontend/src/api/client.ts",
        "frontend/src/api/m2c-generated.ts",
        "frontend/src/api/m2c-schemas.json",
        "frontend/src/features/intake/IntakeFeature.tsx",
        "frontend/src/features/results/Stage1Workspace.tsx",
        "frontend/src/features/results/api.ts",
        "frontend/src/features/results/pg-fixture.json",
        "frontend/src/features/results/results.test.tsx",
        "frontend/src/locales/en-US.json",
        "frontend/src/locales/zh-CN.json",
        "frontend/src/locales/zh-HK.json",
        "frontend/src/styles.css",
        "frontend/src/theme.ts",
        "scripts/m2c_ownership.py",
        "scripts/m2c_projection_architecture.py",
        "scripts/m2c_projection_ownership.py",
        "src/crossborder_compliance/application/stage1_result.py",
        "src/crossborder_compliance/application/workflow_formal.py",
        "src/crossborder_compliance/application/workflow_skeleton.py",
        "src/crossborder_compliance/infrastructure/persistence/workflow_read_projection.py",
        "src/crossborder_compliance/infrastructure/workflow_formal_composition.py",
        "src/crossborder_compliance/interfaces/api/routes/workflow.py",
        "src/crossborder_compliance/workflows/canonical.py",
        "tests/m2c_policy_fixtures.py",
        "tests/conftest.py",
        "tests/test_m1_workflow_api.py",
        "tests/test_m2a_structured_intake.py",
        "tests/test_m2b_integration.py",
        "tests/test_m2c_architecture.py",
        "tests/test_m2c_projection_architecture.py",
        "tests/test_m2c_workflow_contracts.py",
        "tests/test_m2c_workflow_postgres.py",
        "tests/test_phase1l_a_skeleton.py",
        "tests/test_phase1l_b_contracts.py",
        "tests/test_phase1l_b_postgres.py",
    }
)


def overlay(root):
    root = Path(root)
    record = root / "evidence/m2c/c1_approved_owner_overlay.json"
    if not record.exists():
        return True, {}, None
    try:
        data = json.loads(record.read_text())
        source = data["source_sha"]

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

        from scripts.m2d_ownership import overlay as review_overlay
        review_valid, review_paths, review_source = review_overlay(root)
        valid = review_valid and (
            data["base_sha"] == BASE
            and source != BASE
            and ancestor(BASE, source)
            and ancestor(source, "HEAD")
            and set(data["paths"]) == PATHS
        )
        valid = valid and all(
            hashlib.sha256(git("show", source + ":" + p)).hexdigest() == h
            and ((root / p).read_bytes() == git("show", source + ":" + p) or p in review_paths)
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
                "src/crossborder_compliance/domain",
                "evidence/m2a",
                "evidence/m2b",
                "evidence/phase1j",
                "evidence/phase1l_b",
            )
            .decode()
            .splitlines()
        )
        frozen += [
            "ARCHITECTURE_RULES.md",
            "pyproject.toml",
            "frontend/package.json",
            "frontend/package-lock.json",
            "src/crossborder_compliance/workflows/langgraph_adapter.py",
            "evidence/m2c/C0_gate_result.json",
            "evidence/m2c/c0_approved_owner_overlay.json",
        ]
        valid = valid and all(
            (root / p).read_bytes() == git("show", BASE + ":" + p) for p in frozen if p not in review_paths
        )
        delta = set(git("diff", "--name-only", BASE, source).decode().splitlines())
        valid = valid and all(
            p in PATHS or p.startswith(("docs/m2c/", "evidence/m2c/")) for p in delta
        )
        return valid, {**data["paths"], **review_paths}, review_source or source
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError):
        return False, {}, None

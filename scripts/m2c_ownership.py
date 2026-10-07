"""Approved C0 finite owner transfer authenticated against committed Git objects."""

import hashlib
import json
import subprocess
from pathlib import Path

BASE = "42571c7148456f41adb64d2528c169a357214a25"
MIGRATION = "alembic/versions/0014_m2c_formal_result_authority.py"
PATHS = frozenset(
    {
        MIGRATION,
        "alembic/env.py",
        "src/crossborder_compliance/application/formal_result_services.py",
        "src/crossborder_compliance/application/country_compliance_services.py",
        "src/crossborder_compliance/domain/formal_result_contracts.py",
        "src/crossborder_compliance/domain/formal_result_policies.py",
        "src/crossborder_compliance/domain/formal_result_engine.py",
        "src/crossborder_compliance/infrastructure/persistence/formal_result_models.py",
        "src/crossborder_compliance/infrastructure/persistence/formal_result_repository.py",
        "src/crossborder_compliance/infrastructure/persistence/formal_result_governance.py",
        "src/crossborder_compliance/infrastructure/persistence/country_compliance_repository.py",
        "src/crossborder_compliance/infrastructure/persistence/decision_models.py",
        "src/crossborder_compliance/infrastructure/persistence/compliance_profile_governance.py",
        "src/crossborder_compliance/infrastructure/persistence/metadata_repositories.py",
        "src/crossborder_compliance/infrastructure/registry_catalog.py",
        "src/crossborder_compliance/interfaces/api/routes/admin_metadata.py",
        "src/crossborder_compliance/interfaces/api/routes/metadata.py",
        "src/crossborder_compliance/interfaces/api/routes/decisions.py",
        "scripts/m2c_ownership.py",
        "scripts/m2c_architecture_check.py",
        "scripts/m2a_ownership.py",
        "scripts/m2b_ownership.py",
        "tests/test_phase1j_postgres.py",
        "tests/test_m2b_migrations.py",
        "tests/test_m2c_authority_postgres.py",
        "tests/test_m2c_authority_contracts.py",
        "tests/test_m2c_migrations.py",
        "tests/test_m2c_architecture.py",
    }
)


def overlay(root):
    root = Path(root)
    record = root / "evidence/m2c/c0_approved_owner_overlay.json"
    if not record.exists():
        return False, {}, None
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

        valid = (
            data["base_sha"] == BASE
            and source != BASE
            and ancestor(BASE, source)
            and ancestor(source, "HEAD")
            and set(data["paths"]) == PATHS
        )
        valid = valid and all(
            hashlib.sha256(git("show", source + ":" + p)).hexdigest() == h
            and (root / p).read_bytes() == git("show", source + ":" + p)
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
        ]
        frozen += (
            git(
                "ls-tree",
                "-r",
                "--name-only",
                BASE,
                "--",
                "src/crossborder_compliance/domain",
                "src/crossborder_compliance/workflows",
            )
            .decode()
            .splitlines()
        )
        valid = valid and all(
            (root / p).read_bytes() == git("show", BASE + ":" + p) for p in frozen
        )
        delta = set(git("diff", "--name-only", BASE, source).decode().splitlines())
        valid = valid and all(
            p in PATHS or p.startswith(("docs/m2c/", "evidence/m2c/")) for p in delta
        )
        return valid, data["paths"], source
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        return False, {}, None

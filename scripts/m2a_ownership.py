"""Finite M2-A owner transfer proved against committed source, never live approval."""

import hashlib
import json
import subprocess
from pathlib import Path

BASE = "83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1"
MIGRATION = "alembic/versions/0011_m2a_structured_intake.py"
SHARED = frozenset(
    {
        "src/crossborder_compliance/application/context_ports.py",
        "src/crossborder_compliance/application/context_services.py",
        "src/crossborder_compliance/application/ports.py",
        "src/crossborder_compliance/application/workflow_formal.py",
        "src/crossborder_compliance/domain/context_resolution.py",
        "src/crossborder_compliance/infrastructure/persistence/context_models.py",
        "src/crossborder_compliance/infrastructure/persistence/context_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/postgres_repositories.py",
        "src/crossborder_compliance/infrastructure/registry_catalog.py",
        "src/crossborder_compliance/interfaces/api/routes/metadata.py",
        "src/crossborder_compliance/interfaces/api/routes/workflow.py",
        "src/crossborder_compliance/interfaces/api/workflow_app.py",
        "frontend/src/App.tsx",
        "frontend/src/api/client.ts",
        "frontend/src/features/intake/IntakeFeature.tsx",
        "frontend/src/features/intake/api.ts",
        "frontend/src/features/intake/contracts.ts",
        "frontend/src/locales/en-US.json",
        "frontend/src/locales/zh-CN.json",
        "frontend/src/locales/zh-HK.json",
        "scripts/phase1j_ownership.py",
        "scripts/phase1l_b_ownership.py",
        "scripts/m1_phase1lb_ownership.py",
        "scripts/phase1k_a_boundary_check.py",
        "scripts/stage1_alpha_integrity.py",
        "smoke/run_gate.sh",
        "tests/test_phase1j_migrations.py",
        ".github/workflows/m1-alpha.yml",
        MIGRATION,
    }
)


def overlay(root):
    root = Path(root)
    record = root / "evidence/m2a/approved_owner_overlay.json"
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

        from scripts.m2b_ownership import overlay as document_overlay, MIGRATIONS as document_migrations
        if (root / "evidence/m2b/approved_owner_overlay.json").exists():
            document_valid, document_paths, document_source = document_overlay(root)
        else:
            document_valid, document_paths, document_source = True, {}, None
        from scripts.m2c_ownership import overlay as authority_overlay, MIGRATION as authority_migration
        authority_valid, authority_paths, authority_source = authority_overlay(root) if (root / 'evidence/m2c/c0_approved_owner_overlay.json').exists() else (True, {}, None)
        valid = document_valid and authority_valid and (
            data["base_sha"] == BASE
            and ancestor(BASE, source)
            and ancestor(source, "HEAD")
            and source != BASE
            and set(data["paths"]) == SHARED
        )
        valid = valid and all(
            hashlib.sha256(git("show", source + ":" + p)).hexdigest() == h
            and ((root / p).read_bytes() == git("show", source + ":" + p) or p in document_paths or p in authority_paths)
            for p, h in data["paths"].items()
        )
        old = set(
            git("ls-tree", "-r", "--name-only", BASE, "--", "alembic/versions")
            .decode()
            .splitlines()
        )
        now = {str(p.relative_to(root)) for p in (root / "alembic/versions").glob("*.py")}
        valid = (
            valid
            and now == old | {MIGRATION} | (document_migrations if document_paths else set()) | ({authority_migration} if authority_paths else set()) | {p for p in authority_paths if p.startswith("alembic/versions/")}
            and all((root / p).read_bytes() == git("show", BASE + ":" + p) for p in old)
        )
        protected = ["ARCHITECTURE_RULES.md", "frontend/package.json", "frontend/package-lock.json"]
        protected += (
            git(
                "ls-tree",
                "-r",
                "--name-only",
                BASE,
                "--",
                "src/crossborder_compliance/workflows",
                "src/crossborder_compliance/domain",
            )
            .decode()
            .splitlines()
        )
        valid = valid and all(
            (root / p).read_bytes() == git("show", BASE + ":" + p)
            for p in protected
            if p not in SHARED and p not in authority_paths
        )
        delta = set(git("diff", "--name-only", BASE, source).decode().splitlines())

        def allowed(p):
            return (
                p in SHARED
                or p.startswith(
                    (
                        "docs/m2a/",
                        "evidence/m2a/",
                        "artifacts/m2a/",
                        "frontend/scripts/m2a/",
                        "frontend/src/api/m2a-",
                        "frontend/src/features/intake/m2a",
                        "tests/test_m2a_",
                        "scripts/m2a_",
                    )
                )
                or p
                in {
                    "src/crossborder_compliance/application/intake_services.py",
                    "src/crossborder_compliance/application/structured_intake.py",
                    "src/crossborder_compliance/infrastructure/intake_composition.py",
                    "src/crossborder_compliance/infrastructure/persistence/project_intake.py",
                    "src/crossborder_compliance/infrastructure/persistence/structured_intake.py",
                    "src/crossborder_compliance/interfaces/api/routes/intake.py",
                    "frontend/src/features/intake/ProductionIntake.tsx",
                    "frontend/src/features/intake/persistence.ts",
                    "frontend/e2e/m2a.spec.ts",
                    "tests/m2a_worker.py",
                    ".github/workflows/m2a-intake.yml",
                }
            )

        valid = valid and all(allowed(p) for p in delta)
        return valid, {**data["paths"], **document_paths, **authority_paths}, authority_source or document_source or source
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError):
        return False, {}, None


def owned_delta(root):
    valid, _, source = overlay(root)
    if not valid or source is None:
        return set()
    paths = set(
        subprocess.check_output(
            ["git", "diff", "--name-only", BASE, source], cwd=root, text=True
        ).splitlines()
    )
    paths.add("evidence/m2a/approved_owner_overlay.json")
    # Delivery evidence is subsequent to tested source; cannot approve code.
    paths.update(
        str(p.relative_to(root))
        for prefix in ("docs/m2a", "evidence/m2a", "docs/m2b", "evidence/m2b", "docs/m2c", "evidence/m2c", "docs/m2d", "evidence/m2d")
        for p in (Path(root) / prefix).rglob("*")
        if p.is_file()
    )
    return paths


if __name__ == "__main__":
    import sys

    valid, paths, source = overlay(Path(__file__).resolve().parents[1])
    print(
        json.dumps(
            {
                "pass": valid and bool(paths),
                "baseline": BASE,
                "source": source,
                "shared_paths": sorted(paths),
            },
            indent=2,
        )
    )
    sys.exit(not (valid and paths))

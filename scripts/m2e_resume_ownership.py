"""Finite M2-E resume successor; historical R1 proof remains immutable.

Only immutable Git object reads are cached. Every validation rereads live files,
records and ancestry, so caching cannot authorize uncommitted owner changes.
"""

import ast
import hashlib
import io
import json
import subprocess
import tarfile
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

BASE = "df2e2e0b8552ab2172f02ce2d79f1ef911660efb"
FORMAL_BASE = "0f5a40c5ca3a8771624fb38e9380856d79e67342"
R1_SOURCE = "6655b6cbe7711b68979ee7862aa70416f432d850"
RECORD = "evidence/m2e/resume_approved_owner_overlay.json"
R1_RECORD = "evidence/m2e/r1_approved_owner_overlay.json"
# This tuple is generated once from the enumerated implementation file set,
# committed for review, never inferred from runtime changes.
RESUME_PATHS = frozenset(
    (
        ".github/workflows/m2e-external-agent-api.yml",
        "frontend/e2e/m2e.spec.ts",
        "frontend/scripts/m2e/export_contracts.py",
        "frontend/scripts/m2e/uat.py",
        "frontend/src/api/client.ts",
        "frontend/src/api/m2e-generated.ts",
        "frontend/src/api/m2e-schemas.json",
        "frontend/src/features/admin/AdminFeature.tsx",
        "frontend/src/features/admin/admin.css",
        "frontend/src/features/admin/resources.ts",
        "frontend/src/features/integrations/IntegrationClients.tsx",
        "frontend/src/features/integrations/api.ts",
        "frontend/src/features/integrations/integrations.test.tsx",
        "frontend/src/locales/en-US.json",
        "frontend/src/locales/zh-CN.json",
        "frontend/src/locales/zh-HK.json",
        "scripts/m2e_architecture_check.py",
        "scripts/m2e_closure.py",
        "scripts/m2e_r1_ownership.py",
        "scripts/m2e_resume_ownership.py",
        "scripts/phase1kb_closure.py",
        "sdk/openapi/external-v1.json",
        "sdk/python/.gitignore",
        "sdk/python/pyproject.toml",
        "sdk/python/src/crossborder_agent/__init__.py",
        "sdk/python/src/crossborder_agent/client.py",
        "sdk/python/src/crossborder_agent/contracts.py",
        "sdk/python/src/crossborder_agent/external-v1.json",
        "sdk/typescript/.gitignore",
        "sdk/typescript/package.json",
        "sdk/typescript/src/client.ts",
        "sdk/typescript/src/generated.ts",
        "sdk/typescript/test/client.test.mjs",
        "sdk/typescript/tsconfig.json",
        "src/crossborder_compliance/application/integrations.py",
        "src/crossborder_compliance/domain/integrations.py",
        "src/crossborder_compliance/infrastructure/external_composition.py",
        "src/crossborder_compliance/infrastructure/integration_worker.py",
        "src/crossborder_compliance/infrastructure/persistence/integrations.py",
        "src/crossborder_compliance/infrastructure/persistence/webhooks.py",
        "src/crossborder_compliance/interfaces/api/external_openapi.py",
        "src/crossborder_compliance/interfaces/api/main.py",
        "src/crossborder_compliance/interfaces/api/routes/external.py",
        "src/crossborder_compliance/interfaces/api/routes/integrations.py",
        "src/crossborder_compliance/interfaces/api/workflow_app.py",
        "src/crossborder_compliance/workflows/langgraph_adapter.py",
        "tests/test_m2e_architecture_closure.py",
        "tests/test_m2e_checkpointer_concurrency.py",
        "tests/test_m2e_gateway_closure.py",
        "tests/test_m2e_integration_migrations.py",
        "tests/test_m2e_openapi_sdk.py",
        "tests/test_m2e_r1_architecture.py",
        "tests/test_m2e_vertical_postgres.py",
    )
)


def git(root, *args):
    return subprocess.check_output(
        ["git", "-c", "core.quotepath=false", *args], cwd=root, stderr=subprocess.DEVNULL
    )


@lru_cache(maxsize=16)
def blobs(root, sha, paths):
    archive = git(root, "archive", "--format=tar", sha, "--", *paths)
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        return MappingProxyType(
            {entry.name: stream.extractfile(entry).read() for entry in stream if entry.isfile()}
        )


def ancestor(root, first, second):
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", first, second],
            cwd=root,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def stable_runtime(data):
    tree = ast.parse(data)
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_setup_checkpointer"
        ):
            node.body = [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


def overlay(root, r1_paths):
    root = Path(root).resolve()
    try:
        old_bytes = (root / R1_RECORD).read_bytes()
        if old_bytes != git(root, "show", BASE + ":" + R1_RECORD):
            return False, {}, None
        previous = json.loads(old_bytes)
        if previous["source_sha"] != R1_SOURCE or set(previous["paths"]) != r1_paths:
            return False, {}, None
        historical = blobs(str(root), R1_SOURCE, tuple(sorted(r1_paths)))
        if not all(
            hashlib.sha256(historical[p]).hexdigest() == h for p, h in previous["paths"].items()
        ):
            return False, {}, None
        data = json.loads((root / RECORD).read_text())
        source = data["source_sha"]
        paths = r1_paths | RESUME_PATHS
        valid = data["base_sha"] == BASE and data["r1_source_sha"] == R1_SOURCE
        valid = (
            valid
            and ancestor(root, BASE, source)
            and ancestor(root, source, "HEAD")
            and source != BASE
        )
        valid = valid and set(data["paths"]) == paths
        committed = blobs(str(root), source, tuple(sorted(paths)))
        valid = valid and all(
            hashlib.sha256(committed[p]).hexdigest() == h
            and (root / p).read_bytes() == committed[p]
            for p, h in data["paths"].items()
        )
        # Recovery owning contracts are frozen; only enumerated channel/runtime
        # technical files may change. Classification engines/migrations stay R1.
        valid = valid and all(committed[p] == historical[p] for p in r1_paths - RESUME_PATHS)
        adapter = "src/crossborder_compliance/workflows/langgraph_adapter.py"
        valid = valid and stable_runtime(committed[adapter]) == stable_runtime(historical[adapter])
        baseline = (
            git(
                root,
                "ls-tree",
                "-r",
                "--name-only",
                FORMAL_BASE,
                "--",
                "src",
                "alembic/versions",
                "frontend",
                "evidence",
                "scripts",
                ".github",
            )
            .decode()
            .splitlines()
        )
        baseline += ["ARCHITECTURE_RULES.md", "pyproject.toml"]
        original = blobs(str(root), FORMAL_BASE, tuple(sorted(baseline)))
        valid = valid and all(
            (root / p).read_bytes() == original[p] for p in baseline if p not in paths
        )
        delta = set(git(root, "diff", "--name-only", FORMAL_BASE, source).decode().splitlines())
        live = set(git(root, "diff", "--name-only", FORMAL_BASE).decode().splitlines())
        untracked = set(
            git(root, "ls-files", "--others", "--exclude-standard").decode().splitlines()
        )
        valid = valid and all(
            p in paths or p.startswith(("docs/m2e/", "evidence/m2e/"))
            for p in delta | live | untracked
        )
        return valid, data["paths"], source
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        return False, {}, None

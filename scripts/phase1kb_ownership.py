"""Finite approved Phase1K-B extension of the existing registry/gateway and prior owner overlays."""

import hashlib
import json
import subprocess
from pathlib import Path

BASE = "efda0955342de8d1ea36aa0f754d63c9b421fec8"
PATHS = frozenset(
    {
        "scripts/phase1j_architecture_checks.py",
        "scripts/phase1j_ownership.py",
        ".github/workflows/m2d-human-review.yml",
        "scripts/m2a_ownership.py",
        "frontend/index.html",
        ".github/workflows/phase1kb-multi-provider-llm-governance.yml",
        "alembic/versions/0016_phase1kb_multi_provider_llm_governance.py",
        "frontend/e2e/phase1kb.spec.ts",
        "frontend/scripts/phase1kb/export_contracts.py",
        "frontend/scripts/phase1kb/uat.py",
        "frontend/src/api/client.ts",
        "frontend/src/api/m2a-generated.ts",
        "frontend/src/api/m2a-schemas.json",
        "frontend/src/api/phase1kb-generated.ts",
        "frontend/src/api/phase1kb-schemas.json",
        "frontend/src/features/admin/AdminFeature.tsx",
        "frontend/src/features/admin/resources.ts",
        "frontend/src/features/intake/IntakeFeature.tsx",
        "frontend/src/features/intake/contracts.ts",
        "frontend/src/features/intake/persistence.ts",
        "frontend/src/features/models/AISettings.tsx",
        "frontend/src/features/models/ModelProviders.tsx",
        "frontend/src/features/models/api.ts",
        "frontend/src/features/models/models.test.tsx",
        "frontend/src/features/models/selection.test.tsx",
        "frontend/src/locales/en-US.json",
        "frontend/src/locales/zh-CN.json",
        "frontend/src/locales/zh-HK.json",
        "pyproject.toml",
        "scripts/m0_preview/server.py",
        "scripts/m2d_ownership.py",
        "scripts/phase1kb_architecture_check.py",
        "scripts/phase1kb_closure.py",
        "scripts/phase1kb_ownership.py",
        "scripts/phase1kb_real_provider_acceptance.py",
        "src/crossborder_compliance/application/document_ports.py",
        "src/crossborder_compliance/application/document_services.py",
        "src/crossborder_compliance/application/llm_document_extraction.py",
        "src/crossborder_compliance/application/llm_gateway_policy.py",
        "src/crossborder_compliance/application/llm_gateway_services.py",
        "src/crossborder_compliance/application/llm_invocation_policy.py",
        "src/crossborder_compliance/application/llm_invocation_services.py",
        "src/crossborder_compliance/application/llm_model_catalog.py",
        "src/crossborder_compliance/application/model_control_ports.py",
        "src/crossborder_compliance/application/model_control_services.py",
        "src/crossborder_compliance/application/retrieval_services.py",
        "src/crossborder_compliance/domain/contracts.py",
        "src/crossborder_compliance/domain/llm_document_candidates.py",
        "src/crossborder_compliance/domain/llm_gateway.py",
        "src/crossborder_compliance/domain/llm_invocation.py",
        "src/crossborder_compliance/domain/metadata.py",
        "src/crossborder_compliance/domain/model_control.py",
        "src/crossborder_compliance/infrastructure/intake_composition.py",
        "src/crossborder_compliance/infrastructure/llm_document_inputs.py",
        "src/crossborder_compliance/infrastructure/llm_enhancement_composition.py",
        "src/crossborder_compliance/infrastructure/llm_gateway_configuration.py",
        "src/crossborder_compliance/infrastructure/llm_gateway_http.py",
        "src/crossborder_compliance/infrastructure/llm_invocation_governance.py",
        "src/crossborder_compliance/infrastructure/llm_model_catalog_composition.py",
        "src/crossborder_compliance/infrastructure/llm_provider_inspection.py",
        "src/crossborder_compliance/infrastructure/llm_query_expansion.py",
        "src/crossborder_compliance/infrastructure/llm_secrets.py",
        "src/crossborder_compliance/infrastructure/llm_snapshot_pins.py",
        "src/crossborder_compliance/infrastructure/model_control_composition.py",
        "src/crossborder_compliance/infrastructure/persistence/compliance_profile_governance.py",
        "src/crossborder_compliance/infrastructure/persistence/config_admin_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/document_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/llm_gateway_audit.py",
        "src/crossborder_compliance/infrastructure/persistence/llm_metadata_governance.py",
        "src/crossborder_compliance/infrastructure/persistence/metadata_models.py",
        "src/crossborder_compliance/infrastructure/persistence/model_control.py",
        "src/crossborder_compliance/infrastructure/persistence/special_admin_repositories.py",
        "src/crossborder_compliance/infrastructure/registry_catalog.py",
        "src/crossborder_compliance/infrastructure/workflow_formal_composition.py",
        "src/crossborder_compliance/interfaces/api/main.py",
        "src/crossborder_compliance/interfaces/api/model_schemas.py",
        "src/crossborder_compliance/interfaces/api/routes/admin_metadata.py",
        "src/crossborder_compliance/interfaces/api/routes/intake.py",
        "src/crossborder_compliance/interfaces/api/routes/llm_models.py",
        "src/crossborder_compliance/interfaces/api/routes/metadata.py",
        "src/crossborder_compliance/interfaces/api/routes/model_providers.py",
        "src/crossborder_compliance/interfaces/api/routes/workflow.py",
        "tests/phase1kb_http_servers.py",
        "tests/test_phase1kb_architecture.py",
        "tests/test_phase1kb_catalog_postgres.py",
        "tests/test_phase1kb_control_api_postgres.py",
        "tests/test_phase1kb_control_postgres.py",
        "tests/test_phase1kb_document_postgres.py",
        "tests/test_phase1kb_endpoint_security.py",
        "tests/test_phase1kb_http_postgres.py",
        "tests/test_phase1kb_invocation_policy.py",
        "tests/test_phase1kb_metadata_postgres.py",
        "tests/test_phase1kb_migrations.py",
        "tests/test_phase1kb_query_postgres.py",
        "tests/test_phase1kb_secrets.py",
        "tests/test_phase1kb_selection_postgres.py",
        "tests/test_phase1kb_snapshot_postgres.py",
        "跨境數據合規智能體_V3.7_設計一致性檢查與變更摘要.md",
    }
)


def overlay(root):
    root = Path(root)
    record = root / "evidence/phase1kb/approved_owner_overlay.json"
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

        valid = (
            data["base_sha"] == BASE
            and source != BASE
            and ancestor(BASE, source)
            and ancestor(source, "HEAD")
        )
        valid = (
            valid
            and set(data["paths"]) <= PATHS
            and "scripts/phase1kb_ownership.py" in data["paths"]
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
                "src",
                "frontend/src",
                "evidence",
            )
            .decode()
            .splitlines()
        )
        frozen += ["ARCHITECTURE_RULES.md", "frontend/package.json", "frontend/package-lock.json"]
        valid = valid and all(
            (root / p).read_bytes() == git("show", BASE + ":" + p) for p in frozen if p not in PATHS
        )
        delta = set(git("diff", "--name-only", BASE, source).decode().splitlines())
        valid = valid and all(
            p in PATHS
            or p.startswith(("docs/phase1kb/", "evidence/phase1kb/"))
            or p.endswith("V3.7.md")
            for p in delta
        )
        return valid, data["paths"], source
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError):
        return False, {}, None


def preserved_v1_contracts(root, expected):
    """Only the approved optional intake preference/import may extend frozen v1 bytes."""
    current = (Path(root) / "src/crossborder_compliance/domain/contracts.py").read_bytes()
    if current == expected:
        return True
    valid, paths, source = overlay(root)
    if not valid or source is None or "src/crossborder_compliance/domain/contracts.py" not in paths:
        return False
    additions = (
        b"from crossborder_compliance.domain.llm_invocation import AIModelPreference\n",
        b"    ai_model_preference: AIModelPreference = Field(default_factory=AIModelPreference)\n",
    )
    if not all(current.count(line) == 1 for line in additions):
        return False
    for line in additions:
        current = current.replace(line, b"")
    return current == expected

"""Finite integration delta; immutable original-owner provenance."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.phase1l_b_ownership import BASE, VERIFIED_SOURCE, overlay

M1 = "5b1aaf5df05de458a65ead497536b323ecb16ce9"
SYNC = "69a8bc3aefa326523064793f01ca4dedb48000fb"
PATHS = frozenset(
    [
        "scripts/phase1l_b_ownership.py",
        "frontend/scripts/m1/boundary_check.py",
        "scripts/m1_phase1lb_ownership.py",
        "tests/test_m1_phase1lb_ownership.py",
        "evidence/integration/m1-phase1lb/approved_sources.json",
        "src/crossborder_compliance/interfaces/api/workflow_app.py",
        "src/crossborder_compliance/interfaces/api/routes/workflow.py",
        "src/crossborder_compliance/infrastructure/persistence/workflow_read_projection.py",
        "tests/test_m1_workflow_api.py",
        "frontend/scripts/m1/uat.py",
        "frontend/scripts/m1/export_contracts.py",
        "frontend/src/api/m1-schemas.json",
        "frontend/src/api/m1-generated.ts",
        "frontend/src/features/intake/api.ts",
        "frontend/src/features/intake/contracts.ts",
        "frontend/src/features/intake/IntakeFeature.tsx",
        "frontend/src/features/intake/m1.test.tsx",
        "frontend/src/features/intake/workflow.test.tsx",
        "frontend/src/features/analysis/AnalysisPanel.tsx",
        "frontend/src/locales/en-US.json",
        "frontend/src/locales/zh-CN.json",
        "frontend/src/locales/zh-HK.json",
        "frontend/e2e/m1.spec.ts",
        ".github/workflows/m1-alpha.yml",
        "docs/integration/m1-phase1lb/integration_contract.md",
    ]
)


def verify(root):
    root = Path(root)

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root)

    def ancestor(sha):
        return (
            subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=root).returncode
            == 0
        )

    manifest = json.loads(
        (root / "evidence/integration/m1-phase1lb/approved_sources.json").read_text()
    )
    changed = set(git("diff", "--name-only", SYNC).decode().splitlines())
    # Newly added source files must be staged before certification; unrelated
    # pre-existing untracked user reports are not claimed as integration inputs.
    m1_paths = git("diff", "--name-only", BASE, M1).decode().splitlines()

    def allowed_m1(p):
        return p.startswith(("frontend/", "docs/m1/", "artifacts/m1/")) or p in {
            ".github/workflows/m1-alpha.yml",
            ".github/workflows/m0-h5-preview.yml",
        }

    from scripts.m2a_ownership import overlay as intake_overlay, owned_delta
    intake_valid, intake_paths, _ = intake_overlay(root)
    checks = {
        "approved_m2a_owner": intake_valid,
        "exact_manifest": manifest["base_sha"] == BASE
        and manifest["phase1l_b_source"] == VERIFIED_SOURCE
        and manifest["m1_source"] == M1
        and manifest["sync_merge"] == SYNC
        and set(manifest["integration_paths"]) == PATHS,
        "both_tested_sources_and_sync_ancestry": all(
            ancestor(x) for x in (VERIFIED_SOURCE, M1, SYNC)
        ),
        "lb_owner_and_historical_overlay": overlay(root)[0],
        "original_m1_owner": all(allowed_m1(p) for p in m1_paths),
        "integration_exact_path_set": changed <= PATHS | owned_delta(root),
        "frozen_domain_migrations_rules": set(git(
            "diff", "--name-only",
            BASE,
            "--",
            "src/crossborder_compliance/domain",
            "alembic",
            "ARCHITECTURE_RULES.md",
        ).decode().splitlines()) <= set(intake_paths),
        "original_overlay_unchanged": (
            root / "evidence/phase1l_b/approved_owner_overlay.json"
        ).read_bytes()
        == git("show", VERIFIED_SOURCE + ":evidence/phase1l_b/approved_owner_overlay.json"),
    }
    return {"pass": all(checks.values()), "checks": checks}


if __name__ == "__main__":
    import sys

    result = verify(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    sys.exit(not result["pass"])

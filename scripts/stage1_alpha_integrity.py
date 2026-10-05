"""Integration-only ancestry, source preservation and single-host proof."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = "700951ebb9ebdf33e399158fd3fb53bb4a6c87e7"
DOMAIN_BASE = "14cba25353d9ab7dda84e9620ff3197d9e2a3d1d"
SOURCES = {
    "B": "45af99271559ee6fd1f652e8ad169fc9afb11c55",
    "C": "3f89f1e8f16402f4754b474260cb9022a4bf92c6",
    "D": "22196955fb0167e3a5bce25bcdf9214f6ebeadb7",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def verify():
    checks = {}
    from scripts.phase1j_ownership import overlay
    j_authorized, j_paths, j_source = overlay(ROOT)
    checks["reviewed_j_owner_overlay"] = j_authorized
    for owner, sha in {"H": BASE, **SOURCES}.items():
        checks[f"{owner}_ancestry_preserved"] = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=ROOT,
        ).returncode == 0
    for owner in ("B", "C", "D"):
        track_base = git("merge-base", BASE, SOURCES[owner]).decode().strip()
        paths = git("diff", "--name-only", track_base, SOURCES[owner], "--", "src").decode().splitlines()
        checks[f"{owner}_backend_identical_to_tested_source"] = all(
            (ROOT / path).read_bytes() == git("show", f"{j_source if j_authorized and path in j_paths else SOURCES[owner]}:{path}")
            for path in paths
            if subprocess.run(["git", "cat-file", "-e", f"{SOURCES[owner]}:{path}"], cwd=ROOT,
                              stderr=subprocess.DEVNULL).returncode == 0
        )
    manifest = json.loads((ROOT / "evidence/stage1-alpha/delivery_preservation.json").read_text())
    checks["delivery_evidence_preserved"] = all(
        hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]
        for item in manifest
    )
    checks["one_production_package_lock_build"] = all(
        not (ROOT / "frontend/admin" / path).exists()
        for path in ("package.json", "package-lock.json", "index.html", "vite.config.ts", "src/main.tsx")
    )
    checks["one_react_bootstrap"] = sum(
        path.read_text().count("createRoot(")
        for path in (ROOT / "frontend/src").rglob("*.tsx")
    ) == 1
    canonical = json.loads(git("show", f"{SOURCES['C']}:frontend/package.json"))
    integrated = json.loads((ROOT / "frontend/package.json").read_text())
    checks["canonical_dependencies_unchanged"] = all(
        integrated[field] == canonical[field]
        for field in ("dependencies", "devDependencies", "engines")
    ) and (ROOT / "frontend/package-lock.json").read_bytes() == git(
        "show", f"{SOURCES['C']}:frontend/package-lock.json"
    )
    # Phase1I owns the inherited0009. Stage1-alpha must preserve its entire
    # reviewed Alembic tree byte-for-byte and introduce no migration changes.
    migration_changes = set(git("diff", "--name-only", DOMAIN_BASE, "--", "alembic").decode().splitlines())
    new_files = {str(p.relative_to(ROOT)) for p in (ROOT / "alembic/versions").glob("*.py")} - set(git("ls-tree", "-r", "--name-only", DOMAIN_BASE, "--", "alembic/versions").decode().splitlines())
    checks["no_integration_migration"] = (not migration_changes and not new_files) if not j_paths else j_authorized and migration_changes | new_files <= {"alembic/env.py", "alembic/versions/0010_phase1j_formal_decisions.py"} and all((ROOT / p).read_bytes() == git("show", j_source + ":" + p) for p in migration_changes | new_files)
    checks["one_shared_http_transport"] = "fetch(" not in (ROOT / "frontend/src/features/admin/client.ts").read_text()
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


if __name__ == "__main__":
    result = verify()
    print(json.dumps(result, indent=2))
    raise SystemExit(result["status"] != "PASS")

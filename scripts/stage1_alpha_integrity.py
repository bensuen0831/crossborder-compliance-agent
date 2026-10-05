"""Integration-only ancestry, source preservation and single-host proof."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "700951ebb9ebdf33e399158fd3fb53bb4a6c87e7"
SOURCES = {
    "B": "45af99271559ee6fd1f652e8ad169fc9afb11c55",
    "C": "3f89f1e8f16402f4754b474260cb9022a4bf92c6",
    "D": "22196955fb0167e3a5bce25bcdf9214f6ebeadb7",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def verify():
    checks = {}
    for owner, sha in {"H": BASE, **SOURCES}.items():
        checks[f"{owner}_ancestry_preserved"] = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=ROOT,
        ).returncode == 0
    for owner in ("B", "C", "D"):
        track_base = git("merge-base", BASE, SOURCES[owner]).decode().strip()
        paths = git("diff", "--name-only", track_base, SOURCES[owner], "--", "src").decode().splitlines()
        checks[f"{owner}_backend_identical_to_tested_source"] = all(
            (ROOT / path).read_bytes() == git("show", f"{SOURCES[owner]}:{path}")
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
    checks["canonical_dependencies_unchanged"] = all(
        (ROOT / "frontend" / path).read_bytes() == git("show", f"{SOURCES['C']}:frontend/{path}")
        for path in ("package.json", "package-lock.json")
    )
    checks["no_integration_migration"] = not git("diff", "--name-only", BASE, "--", "alembic").strip()
    checks["one_shared_http_transport"] = "fetch(" not in (ROOT / "frontend/src/features/admin/client.ts").read_text()
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


if __name__ == "__main__":
    result = verify()
    print(json.dumps(result, indent=2))
    raise SystemExit(result["status"] != "PASS")

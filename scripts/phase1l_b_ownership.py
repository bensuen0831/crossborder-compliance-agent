"""Finite authorized L-B transfer of the existing runtime adapter only."""

import hashlib
import json
import subprocess
from pathlib import Path

BASE = "f1353372a1d8894535dc71765e3cd62597619fd5"
SHARED = {"src/crossborder_compliance/workflows/langgraph_adapter.py"}


def overlay(root):
    root = Path(root)
    record = root / "evidence/phase1l_b/approved_owner_overlay.json"
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

        valid = (
            data["base_sha"] == BASE
            and source != BASE
            and ancestor(BASE, source)
            and ancestor(source, "HEAD")
            and set(data["paths"]) == SHARED
        )
        valid = valid and all(
            hashlib.sha256(git("show", source + ":" + p)).hexdigest() == h
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
            and old == now
            and all((root / p).read_bytes() == git("show", BASE + ":" + p) for p in old)
        )
        valid = valid and (root / "ARCHITECTURE_RULES.md").read_bytes() == git(
            "show", BASE + ":ARCHITECTURE_RULES.md"
        )
        valid = valid and not git(
            "diff", BASE, "--", "frontend", "alembic", "src/crossborder_compliance/domain"
        )
        return valid, data["paths"], source
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError):
        return False, {}, None

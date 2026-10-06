"""Finite authorized L-B transfer of the existing runtime adapter only."""

import hashlib
import json
import subprocess
from pathlib import Path

BASE = "f1353372a1d8894535dc71765e3cd62597619fd5"
SHARED = {"src/crossborder_compliance/workflows/langgraph_adapter.py"}
VERIFIED_SOURCE = "019a7f39767bef81e3078ad0efe2f4d59374799d"


def owner_provenance(root, source=VERIFIED_SOURCE):
    """Prove the reviewed owner's boundary, independent of later owners."""
    if source != VERIFIED_SOURCE:
        return False

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL)

    return (
        subprocess.run(["git", "merge-base", "--is-ancestor", BASE, source], cwd=root).returncode
        == 0
        and subprocess.run(
            ["git", "merge-base", "--is-ancestor", source, "HEAD"], cwd=root
        ).returncode
        == 0
        and not git(
            "diff",
            BASE,
            source,
            "--",
            "frontend",
            "alembic",
            "src/crossborder_compliance/domain",
            "ARCHITECTURE_RULES.md",
        )
    )


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
            and ancestor(source, VERIFIED_SOURCE)
            and owner_provenance(root)
            and set(data["paths"]) == SHARED
        )
        valid = valid and all(
            hashlib.sha256(git("show", source + ":" + p)).hexdigest() == h
            and (root / p).read_bytes() == git("show", source + ":" + p)
            for p, h in data["paths"].items()
        )
        old = set(
            git("ls-tree", "-r", "--name-only", BASE, "--", "alembic/versions")
            .decode()
            .splitlines()
        )
        now = {str(p.relative_to(root)) for p in (root / "alembic/versions").glob("*.py")}
        from scripts.m2a_ownership import overlay as intake_overlay, MIGRATION as intake_migration
        intake_valid, intake_paths, _ = intake_overlay(root)
        valid = (
            valid and intake_valid
            and old | ({intake_migration} if intake_paths else set()) == now
            and all((root / p).read_bytes() == git("show", BASE + ":" + p) for p in old)
        )
        valid = valid and (root / "ARCHITECTURE_RULES.md").read_bytes() == git(
            "show", BASE + ":ARCHITECTURE_RULES.md"
        )
        # Current Domain/Alembic/Rules remain frozen; frontend provenance is
        # proved against the exact L-B source above, not a later M1 descendant.
        frozen_changes = set(git("diff", "--name-only", BASE, "--", "alembic", "src/crossborder_compliance/domain").decode().splitlines())
        valid = valid and frozen_changes <= set(intake_paths)
        return valid, data["paths"], source
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError):
        return False, {}, None

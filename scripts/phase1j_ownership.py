"""Finite J owner transfer, authenticated against committed Git objects.

Earlier manifests stay intact. No SDK/workflow or historical migration owner
can be reassigned by this overlay, and live hashes never create approval.
"""

import hashlib
import json
import subprocess
from pathlib import Path

BASE = "c43ab49f408a1e70c01cd637b327968538d98e23"
ROUND2 = "594be84cfc471af4c12f28600b22cffb66f830f7"
SHARED = {
    "ARCHITECTURE_RULES.md",
    "scripts/architecture_rule_check.py",
    "scripts/verify_full_pytest.py",
    "smoke/run_gate.sh",
    "alembic/env.py",
    "src/crossborder_compliance/application/country_compliance_services.py",
    "src/crossborder_compliance/infrastructure/compliance_profile_worker.py",
    "src/crossborder_compliance/infrastructure/persistence/compliance_profile_governance.py",
    "src/crossborder_compliance/infrastructure/persistence/country_compliance_repository.py",
    "src/crossborder_compliance/infrastructure/persistence/metadata_repositories.py",
    "src/crossborder_compliance/infrastructure/registry_catalog.py",
    "src/crossborder_compliance/interfaces/api/main.py",
    "src/crossborder_compliance/interfaces/api/routes/admin_metadata.py",
    "src/crossborder_compliance/interfaces/api/routes/metadata.py",
}
MIGRATION = "alembic/versions/0010_phase1j_formal_decisions.py"


def overlay(root):
    root = Path(root)
    file = root / "evidence/phase1j/approved_owner_overlay.json"
    if not file.exists():
        return True, {}, None
    try:
        record = json.loads(file.read_text())
        source = record["source_sha"]

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
            record["base_sha"] == BASE
            and record["round2_sha"] == ROUND2
            and ancestor(ROUND2, BASE)
            and ancestor(BASE, source)
            and ancestor(source, "HEAD")
            and set(record["paths"]) == SHARED | {MIGRATION}
        )
        valid = valid and all(
            hashlib.sha256(git("show", source + ":" + p)).hexdigest() == h
            for p, h in record["paths"].items()
        )
        old = set(
            git("ls-tree", "-r", "--name-only", BASE, "--", "alembic/versions")
            .decode()
            .splitlines()
        )
        now = set(str(p.relative_to(root)) for p in (root / "alembic/versions").glob("*.py"))
        from scripts.m2a_ownership import overlay as intake_overlay, MIGRATION as intake_migration
        intake_valid, intake_paths, _ = intake_overlay(root)
        valid = (
            valid and intake_valid
            and now == old | {MIGRATION} | ({intake_migration} if intake_paths else set())
            and all((root / p).read_bytes() == git("show", BASE + ":" + p) for p in old)
        )
        valid = valid and (root / "ARCHITECTURE_RULES.md").read_bytes().startswith(
            git("show", BASE + ":ARCHITECTURE_RULES.md")
        )
        valid = valid and (
            root / "src/crossborder_compliance/domain/contracts.py"
        ).read_bytes() == git("show", BASE + ":src/crossborder_compliance/domain/contracts.py")
        return valid, record["paths"], source
    except (KeyError, ValueError, OSError, subprocess.CalledProcessError):
        return False, {}, None

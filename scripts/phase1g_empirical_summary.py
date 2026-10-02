"""Publish measured gate identities and counts through the GitHub Checks API."""

import hashlib
import json
import os
from pathlib import Path


def main():
    folder = Path(os.environ["EVIDENCE_DIR"])

    def read(name):
        return json.loads((folder / name).read_text())

    schemas = {}
    for phase in ("b", "c", "d", "e", "f", "g"):
        value = read(f"phase1{phase}_schema_check.json")
        assertions = value.get("checks", value.get("assertions"))
        schemas[f"phase1{phase}"] = {
            "pass": value["pass"],
            "passed": sum(assertions.values()),
            "total": len(assertions),
        }
    runtime = read("runtime_verify.json")
    architecture = read("architecture_rule_check.json")
    pytest = read("pytest_full_summary.json")
    identity = read("ci_run_evidence.json")
    full_log = folder / "ci_complete.log"
    summary = {
        "phase": "1G",
        "run_id": identity["run_id"],
        "attempt": identity["run_attempt"],
        "tested_pr_head_sha": identity["tested_pr_head_sha"],
        "runner_merge_sha": identity["runner_checkout_sha"],
        "alembic_head": read("phase1g_schema_check.json")["revision"],
        "pytest": pytest,
        "schema_gates": schemas,
        "architecture": {k: architecture[k] for k in ("pass", "passed", "total")},
        "runtime": {
            "pass": runtime["all_mandatory_assertions_pass"],
            "passed": sum(runtime["assertions"].values()),
            "total": len(runtime["assertions"]),
        },
        "full_gate_log": {
            "filename": full_log.name,
            "bytes": full_log.stat().st_size,
            "sha256": hashlib.sha256(full_log.read_bytes()).hexdigest(),
        },
    }
    summary["pass"] = (
        pytest["pass"]
        and architecture["pass"]
        and summary["runtime"]["pass"]
        and all(gate["pass"] for gate in schemas.values())
    )
    (folder / "phase1g_empirical_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    manifest = {
        path.name: {
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(folder.iterdir())
        if path.is_file() and path.name != "evidence_file_manifest.json"
    }
    (folder / "evidence_file_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # A small measured notice allows read-only verification without archive redirects.
    value = json.dumps(summary, separators=(",", ":"))
    print("::notice title=Phase1G empirical gate::PHASE1G_EMPIRICAL_SUMMARY=" + value)
    raise SystemExit(0 if summary["pass"] else 2)


if __name__ == "__main__":
    main()

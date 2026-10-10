"""Measure strict closure floors and exact checkout identity, without archiving provider inputs."""

import argparse
import json
import os
import subprocess
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("gate", choices=("backend", "frontend"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--frontend", type=Path)
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--m0-browser", type=Path)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    expected = os.environ.get("EXPECTED_PR_HEAD")
    if expected:
        assert head == expected, "Exact-head identity mismatch"
    result = dict(
        tested_pr_head_sha=expected,
        runner_checkout_sha=head,
        final_sha=head,
        exact_head_verified=expected is not None,
    )
    if args.gate == "backend":
        backend = read(args.directory / "pytest_full_summary.json")
        assert backend["pass"] and backend["passed"] >= 763
        assert all(backend[k] == 0 for k in ("skipped", "failed", "errors", "deselected"))
        runtime = read(args.directory / "runtime_verify.json")
        assert runtime["all_mandatory_assertions_pass"]
        assert len(runtime["assertions"]) == 25 and all(runtime["assertions"].values())
        architecture = [
            read(args.directory / filename)
            for filename in (
                "architecture_rule_check_stdout.json",
                "m2a_architecture_check.json",
                "m2b_architecture_check.json",
                "m2c_architecture.json",
                "m2c_projection_architecture.json",
                "m2d_architecture.json",
                "phase1kb_architecture.json",
            )
        ]
        assert all(x["passed"] == x["total"] for x in architecture)
        total = sum(x["total"] for x in architecture)
        assert total >= 269
        from alembic.script import ScriptDirectory

        heads = ScriptDirectory("alembic").get_heads()
        from crossborder_compliance.infrastructure.persistence.migration_lineage import revision_at_or_after
        assert len(heads) == 1 and revision_at_or_after(heads[0], "0016_phase1kb_multi_provider_llm_governance")
        migration = read("artifacts/phase1kb/migration_dual_path.json")
        assert all(
            migration[key]
            for key in (
                "fresh",
                "exact0015_upgrade",
                "schema_equivalence",
                "frozen_migrations_unchanged",
                "empty_downgrade_reupgrade",
                "authoritative_pins_transactional_refusal",
            )
        )
        result.update(
            backend=backend,
            runtime_passed=25,
            architecture_passed=total,
            architecture_total=total,
            migration=migration,
            alembic=heads[0],
        )
    else:
        ui = read(args.frontend)
        assert ui["numPassedTests"] >= 130 and ui["numFailedTests"] == ui["numPendingTests"] == 0
        # M0 owns an insufficient-evidence fixture; M1/KB use sufficient inputs.
        # Measure both original matrices without mixing fixture semantics.
        browsers = ((read(args.browser), 21), (read(args.m0_browser), 36))
        counts = {}

        def walk(suites):
            for suite in suites:
                for spec in suite.get("specs", []):
                    for test in spec["tests"]:
                        assert test["results"] and all(
                            r["retry"] == 0 and r["status"] == "passed" for r in test["results"]
                        )
                        file = Path(spec["file"]).name
                        counts[file] = counts.get(file, 0) + 1
                walk(suite.get("suites", []))

        for browser, expected_count in browsers:
            stats = browser["stats"]
            assert not browser.get("errors")
            assert stats["expected"] == expected_count
            assert stats["unexpected"] == stats["skipped"] == stats["flaky"] == 0
            walk(browser["suites"])
        assert counts == {
            "phase1kb.spec.ts": 6,
            "knowledge.spec.ts": 36,
            **{f"{stage}.spec.ts": 3 for stage in ("m2d", "m2c", "m2b", "m2a", "m1")},
        }
        result.update(
            frontend_passed=ui["numPassedTests"],
            browser_counts=counts,
            retry_count=0,
            locales=["zh-CN", "zh-HK", "en-US"],
            quality="PASS",
        )
    args.directory.mkdir(parents=True, exist_ok=True)
    (args.directory / f"{args.gate}_measured.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

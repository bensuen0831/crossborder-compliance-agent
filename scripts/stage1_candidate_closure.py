"""Measured R1.1 recovery gates; not a Full Stage1 business-matrix PASS."""

import argparse
import json
import os
import subprocess
from pathlib import Path

from scripts.stage1_candidate_architecture import check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("gate", choices=("backend", "frontend"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--frontend", type=Path)
    parser.add_argument("--browser", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    expected = os.getenv("EXPECTED_PR_HEAD")
    assert expected == sha, "Exact checkout identity required"
    read = lambda p: json.loads(p.read_text())
    result = dict(
        runner_checkout_sha=sha,
        tested_source_sha=sha,
        stage2_started=False,
        paid_internet_llm="NOT EXECUTED",
        full_stage1_matrix_started=False,
    )
    if args.gate == "backend":
        measured = read(args.directory / "backend_measured.json")
        assert measured["backend"]["passed"] >= 910
        assert measured["architecture_passed"] == measured["architecture_total"] >= 331
        assert measured["runtime_passed"] == 25
        assert measured["alembic"] == "0019_stage1_candidate_governance"
        checks = check(root)
        assert len(checks) == 24 and all(checks.values())
        migration = read(args.directory / "candidate_governance_migration_measured.json")
        assert migration["head"] == measured["alembic"]
        assert all(
            migration[k]
            for k in (
                "fresh",
                "exact0018_upgrade",
                "schema_equivalence",
                "legacy_audit_unchanged",
                "historical_snapshot_unchanged",
                "safe_downgrade",
                "safe_reupgrade",
                "retained_authority_downgrade_refused",
                "frozen_migrations_unchanged",
            )
        )
        result.update(
            backend=measured["backend"],
            architecture_passed=measured["architecture_passed"],
            architecture_total=measured["architecture_total"],
            runtime_passed=25,
            migration=migration,
            additive_owner_checks=checks,
        )
    else:
        ui, browser = read(args.frontend), read(args.browser)
        assert ui["numPassedTests"] >= 141
        assert ui["numFailedTests"] == ui["numPendingTests"] == 0
        assert not browser.get("errors")
        stats = browser["stats"]
        assert stats["expected"] == 5
        assert stats["unexpected"] == stats["skipped"] == stats["flaky"] == 0
        cases = []

        def walk(suites):
            for suite in suites:
                for spec in suite.get("specs", []):
                    for test in spec["tests"]:
                        assert test["results"] and len(test["results"]) == 1
                        assert (
                            test["results"][0]["status"] == "passed"
                            and test["results"][0]["retry"] == 0
                        )
                        cases.append(spec["title"])
                walk(suite.get("suites", []))

        walk(browser["suites"])
        assert len(cases) == 5
        for locale in ("zh-CN", "zh-HK", "en-US"):
            assert any(locale in title and "ACCEPT" in title for title in cases)
        for action in ("REJECT", "EDIT"):
            assert any(action in title for title in cases)
        result.update(
            frontend_passed=ui["numPassedTests"],
            focused_browser_passed=5,
            browser_retries=0,
            cases=cases,
        )
    result["decision"] = "PASS"
    args.directory.mkdir(parents=True, exist_ok=True)
    (args.directory / ("candidate_" + args.gate + "_measured.json")).write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

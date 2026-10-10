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
        assert backend["pass"] and backend["passed"] >= 893
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
                "m2e_r1_architecture.json",
                "m2e_architecture.json",
            )
        ]
        assert all(x["passed"] == x["total"] for x in architecture)
        total = sum(x["total"] for x in architecture)
        assert total >= 307
        from alembic.script import ScriptDirectory

        heads = ScriptDirectory("alembic").get_heads()
        assert heads == ["0018_phase1h_multijurisdiction_classification_identity"]
        migration = read(args.directory / "migration_measured.json")
        assert all(
            migration[k]
            for k in (
                "fresh",
                "exact0016_to0017_to0018",
                "exact0017_upgrade",
                "schema_equivalence",
                "legacy_row_and_digest_unchanged",
                "safe_downgrade",
                "reupgrade",
                "two_jurisdictions_persist",
                "same_jurisdiction_duplicate_rejected",
                "unsafe_downgrade_transactionally_refused",
                "predicate_unchanged",
            )
        )
        import hashlib

        frozen = {}
        for path in sorted(Path("alembic/versions").glob("00*.py")):
            prefix = int(path.name[:4])
            if prefix > 17:
                continue
            ref = (
                "b7b7602a58581b6316510e184300684cfa6d8036"
                if prefix == 17
                else "0f5a40c5ca3a8771624fb38e9380856d79e67342"
            )
            original = subprocess.check_output(["git", "show", ref + ":" + path.as_posix()])
            assert original == path.read_bytes(), "Frozen migration identity changed"
            frozen[path.name] = hashlib.sha256(original).hexdigest()
        migration.update(frozen_0001_0016=True, unchanged_0017=True, frozen_digests=frozen)
        integration = read(args.directory / "integration_migration_measured.json")
        assert all(integration.values())
        (args.directory / "migration_validation.json").write_text(
            json.dumps(
                {**result, "classification": migration, "integration": integration, "pass": True},
                indent=2,
            )
            + "\n"
        )
        for filename in (
            "external_vertical_validation.json",
            "external_review_validation.json",
            "ui_api_parity.json",
        ):
            measured = read(args.directory / filename)
            assert measured["runner_checkout_sha"] == head
        parity = read(args.directory / "ui_api_parity.json")
        assert all(
            parity[k]
            for k in (
                "all_structured_fields_equal",
                "canonical_input_channel_exercised",
                "intake_adapter_equal",
                "canonical_document_universe_equal",
                "confirmed_input_and_snapshot_equal",
                "model_preferences_equal",
            )
        )
        assert (
            read(args.directory / "external_review_validation.json")["workflow_status"]
            == "REVIEW_REQUIRED"
        )
        vertical = read(args.directory / "external_vertical_validation.json")
        assert (
            vertical["external_successor_snapshot"]
            and vertical["historical_result_unchanged_after_successor"]
        )
        import xml.etree.ElementTree as ET

        cases = ET.parse(args.directory / "pytest_full.xml").findall(".//testcase")
        security = [
            case for case in cases if case.attrib.get("classname", "").startswith("tests.test_m2e_")
        ]
        assert len(security) >= 66 and all(
            case.find("failure") is None
            and case.find("error") is None
            and case.find("skipped") is None
            for case in security
        )
        (args.directory / "security_validation.json").write_text(
            json.dumps(
                {
                    **result,
                    "passed_m2e_tests": len(security),
                    "classes": sorted({x.attrib["classname"] for x in security}),
                    "paid_internet_llm": "NOT EXECUTED",
                    "pass": True,
                },
                indent=2,
            )
            + "\n"
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
        assert ui["numPassedTests"] >= 135 and ui["numFailedTests"] == ui["numPendingTests"] == 0
        # M0 owns an insufficient-evidence fixture; M1/KB use sufficient inputs.
        # Measure both original matrices without mixing fixture semantics.
        browsers = ((read(args.browser), 24), (read(args.m0_browser), 36))
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
            "m2e.spec.ts": 3,
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

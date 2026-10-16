"""Require exact sources and all collected KB tests, locales and capacity kinds."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def one(root, filename):
    paths = list(root.rglob(filename))
    if len(paths) != 1:
        raise ValueError("KB01_CI_MISSING_OR_AMBIGUOUS_ARTIFACT:" + filename)
    return paths[0]


def browser(path, count):
    result = json.loads(path.read_text())
    stats = result["stats"]
    if stats["expected"] != count or any(stats[key] for key in ("unexpected", "flaky", "skipped")):
        raise ValueError("KB01_BROWSER_INCOMPLETE")
    cases = []

    def visit(suite):
        for spec in suite.get("specs", []):
            for test in spec["tests"]:
                runs = test["results"]
                if len(runs) != 1 or runs[0]["status"] != "passed" or runs[0]["retry"] != 0:
                    raise ValueError("KB01_BROWSER_RETRY_OR_NONPASS")
                cases.append(spec["title"])
        for child in suite.get("suites", []):
            visit(child)

    for suite in result["suites"]:
        visit(suite)
    if len(cases) != count or len(set(cases)) != count:
        raise ValueError("KB01_BROWSER_CASE_IDENTITY_MISMATCH")
    return cases


def verify(root, expected):
    frontend_directories = list(root.glob("kb01-management-browser-*"))
    if len(frontend_directories) != 1:
        raise ValueError("KB01_FRONTEND_ARTIFACT_IDENTITY_MISMATCH")
    roots = {
        "backend": one(root, "collected.txt").parent,
        "frontend": frontend_directories[0],
        "capacity": one(root, "SINGLE.json").parent,
    }
    # Capacity's measured directory is nested beneath its job artifacts.
    roots["capacity"] = roots["capacity"].parent
    identities = {}
    for name, directory in roots.items():
        actual = one(directory, "runner_checkout_sha.txt").read_text().strip()
        if actual != expected:
            raise ValueError("KB01_RUNNER_CHECKOUT_MISMATCH:" + name)
        identities[name] = actual
    collected = {
        line.split("::", 1)[0][:-3].replace("/", ".") + "::" + line.split("::", 1)[1]
        for line in one(roots["backend"], "collected.txt").read_text().splitlines()
        if line.startswith("tests/") and ".py::" in line
    }
    executed = []
    for case in ET.parse(one(roots["backend"], "pytest.xml")).iter("testcase"):
        if any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
            raise ValueError("KB01_BACKEND_NONPASS")
        executed.append(case.attrib["classname"] + "::" + case.attrib["name"])
    if not collected or set(executed) != collected or len(executed) != len(collected):
        raise ValueError("KB01_BACKEND_COLLECTED_EXECUTED_MISMATCH")
    frontend = json.loads(one(roots["frontend"], "unit.json").read_text())
    if (
        frontend["numPassedTests"] < 165
        or any(
            frontend.get(key, 0) for key in ("numFailedTests", "numPendingTests", "numTodoTests")
        )
        or frontend["numTotalTests"] != frontend["numPassedTests"]
    ):
        raise ValueError("KB01_FRONTEND_NONPASS_OR_REDUCED")
    locale_cases = browser(one(roots["frontend"], "browser.json"), 5)
    if not all(
        any(locale in title for title in locale_cases) for locale in ("zh-CN", "zh-HK", "en-US")
    ):
        raise ValueError("KB01_LOCALE_COVERAGE_MISSING")
    capacity_cases = browser(one(roots["capacity"], "browser.json"), 4)
    capacity = {}
    for kind in ("SINGLE", "RAR4", "RAR5", "ZIP"):
        measured = json.loads(one(roots["capacity"], kind + ".json").read_text())
        if (
            measured["status"] != "PASS"
            or measured["runtime"] != "READY"
            or measured["publication"] != "ACTIVE"
            or measured["browser_retries"] != 0
        ):
            raise ValueError("KB01_CAPACITY_NONPASS:" + kind)
        if measured["bytes"] <= (500 * 1024**2 if kind == "SINGLE" else 1024**3):
            raise ValueError("KB01_CAPACITY_FLOOR_NOT_MET:" + kind)
        capacity[kind] = measured
    return {
        "decision": "PASS",
        "runner_checkout_shas": identities,
        "backend_test_ids": sorted(collected),
        "frontend_passed": frontend["numPassedTests"],
        "management_browser_test_ids": locale_cases,
        "capacity_browser_test_ids": capacity_cases,
        "capacity": capacity,
        "browser_retries": 0,
        "limitations": [
            "Existing eleven regression workflows remain independently mandatory",
            "Real regulatory legal acceptance remains externally blocked",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.artifacts, args.expected_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("All KB01 collected tests, exact job sources, locale and capacity identities verified.")

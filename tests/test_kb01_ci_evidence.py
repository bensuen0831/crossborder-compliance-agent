"""A green job cannot substitute missing tests, source identity or capacity evidence."""

import copy
import json

import pytest

from scripts.kb01.verify_ci import verify


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def artifacts(tmp_path):
    backend = tmp_path / "kb01-focused-postgres-1"
    frontend = tmp_path / "kb01-management-browser-1"
    capacity = tmp_path / "kb01-capacity-browser-1"
    for directory in (backend, frontend, capacity):
        directory.mkdir()
        (directory / "runner_checkout_sha.txt").write_text("a" * 40)
    (backend / "collected.txt").write_text("tests/test_boundary.py::test_scope\n")
    (backend / "pytest.xml").write_text(
        '<testsuite><testcase classname="tests.test_boundary" name="test_scope"/></testsuite>'
    )
    put(frontend / "unit.json", {"numPassedTests": 165, "numTotalTests": 165})

    def browser(names):
        return {
            "stats": {"expected": len(names), "unexpected": 0, "flaky": 0, "skipped": 0},
            "suites": [
                {
                    "specs": [
                        {"title": name, "tests": [{"results": [{"status": "passed", "retry": 0}]}]}
                        for name in names
                    ]
                }
            ],
        }

    put(
        frontend / "browser.json",
        browser(
            ["management " + locale for locale in ("zh-CN", "zh-HK", "en-US")]
            + ["catalogue explicit human mapping", "governed country and category lifecycle"]
        ),
    )
    put(
        capacity / "browser.json",
        browser(["capacity " + kind for kind in ("SINGLE", "RAR4", "RAR5", "ZIP")]),
    )
    for kind in ("SINGLE", "RAR4", "RAR5", "ZIP"):
        put(
            capacity / "measured" / (kind + ".json"),
            {
                "status": "PASS",
                "runtime": "READY",
                "publication": "ACTIVE",
                "browser_retries": 0,
                "bytes": 1024**3 + 1,
            },
        )
    return tmp_path, backend, frontend, capacity


def test_ci_aggregation_requires_complete_exact_source_evidence(artifacts):
    root, _, _, _ = artifacts
    assert verify(root, "a" * 40)["decision"] == "PASS"


@pytest.mark.parametrize("tamper", ["source", "skipped", "missing_test", "retry", "small_archive"])
def test_ci_aggregation_rejects_green_but_incomplete_or_wrong_source(artifacts, tamper):
    root, backend, frontend, capacity = artifacts
    if tamper == "source":
        (frontend / "runner_checkout_sha.txt").write_text("b" * 40)
    elif tamper == "skipped":
        path = backend / "pytest.xml"
        path.write_text(path.read_text().replace("/>", "><skipped/></testcase>"))
    elif tamper == "missing_test":
        with (backend / "collected.txt").open("a") as output:
            output.write("tests/test_boundary.py::test_also_required\n")
    else:
        path = capacity / "measured/RAR5.json"
        value = copy.deepcopy(json.loads(path.read_text()))
        value["browser_retries" if tamper == "retry" else "bytes"] = 1
        put(path, value)
    with pytest.raises(ValueError, match="KB01_"):
        verify(root, "a" * 40)


@pytest.mark.parametrize(
    "origin",
    [
        "http://example.com:15173",
        "http://user:pass@localhost:15173",
        "http://localhost:15173/?secret=redacted",
        "http://localhost:15173/path",
    ],
)
def test_uat_cannot_configure_nonlocal_or_credentialed_cors(monkeypatch, origin):
    from scripts.kb01.uat import upload_browser_origin

    monkeypatch.setenv("M0_FRONTEND_URL", origin)
    with pytest.raises(ValueError, match="KB01_UAT_REQUIRES_EXACT_LOOPBACK_ORIGIN"):
        upload_browser_origin()


def test_uat_uses_exact_isolated_browser_origin(monkeypatch):
    from scripts.kb01.uat import upload_browser_origin

    monkeypatch.setenv("M0_FRONTEND_URL", "http://127.0.0.1:15175")
    assert upload_browser_origin() == "http://127.0.0.1:15175"

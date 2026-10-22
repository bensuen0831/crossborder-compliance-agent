"""Lifecycle safety: do not reset other data or publish synthetic identity."""

import json
import stat

import pytest

from scripts.kb01 import rc1


def test_rc1_reset_wrong_instance_never_stops_or_removes_resources(tmp_path, monkeypatch):
    state = tmp_path / "rc1"
    monkeypatch.setattr(
        "sys.argv",
        ["rc1", "reset", "--state-dir", str(state), "--confirm-reset", "not-the-instance"],
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("No Docker/process mutation may occur before reset authorization")

    monkeypatch.setattr(rc1, "docker", forbidden)
    monkeypatch.setattr(rc1, "stop", forbidden)
    with pytest.raises(SystemExit) as result:
        rc1.main()
    assert result.value.code == 1
    assert stat.S_IMODE((state / "private.json").stat().st_mode) == 0o600
    assert stat.S_IMODE(state.stat().st_mode) == 0o700


def test_rc1_environment_pins_owned_database_loopback_and_both_uat_guards(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://do-not-touch-production")
    monkeypatch.setenv("HTTPS_PROXY", "http://test-proxy.invalid:8080")
    value = rc1.environment(tmp_path, {"postgres_password": "synthetic-only"})
    assert "@127.0.0.1:65432/kb01_rc1" in value["DATABASE_URL"]
    assert value["M0_LOCAL_UAT"] == value["KB01_LOCAL_UAT"] == "1"
    assert value["M0_API_TARGET"] == "http://127.0.0.1:18010"
    assert value["M0_FRONTEND_URL"] == "http://127.0.0.1:15173"
    assert value["HTTPS_PROXY"] == "http://test-proxy.invalid:8080"


def test_rc1_settings_reuse_the_same_private_test_identity_on_restart(tmp_path):
    first = rc1.settings(tmp_path)
    second = rc1.settings(tmp_path)
    assert first == second
    assert json.loads((tmp_path / "private.json").read_text()) == first

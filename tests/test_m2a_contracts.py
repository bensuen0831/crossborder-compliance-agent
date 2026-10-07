"""Canonical schema-derived intake bounds and additional architecture boundaries."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from crossborder_compliance.application.intake_services import IntakeFacts
from crossborder_compliance.application.structured_intake import StructuredIntakeBinding
from scripts.m2a_architecture_check import check


def test_canonical_intake_authority_and_bounds():
    for field in (
        "tenant_id",
        "project_id",
        "provenance",
        "confirmed",
        "policy_id",
        "workflow_run_id",
        "final_path",
    ):
        with pytest.raises(ValidationError):
            IntakeFacts.model_validate({"analysis_as_of_date": "2026-01-01", field: "injected"})
    with pytest.raises(ValidationError):
        IntakeFacts(analysis_as_of_date="2026-01-01", business_purpose="x" * 4097)
    with pytest.raises(ValidationError):
        IntakeFacts(analysis_as_of_date="2026-01-01", selected_products=["x"] * 129)


def test_generic_binding_type_validation_not_business_mapping():
    binding = StructuredIntakeBinding(field_path="data_volume", value_type="integer")
    assert binding.normalize("3") == 3
    with pytest.raises(ValueError):
        binding.normalize("invented")
    with pytest.raises(ValidationError):
        StructuredIntakeBinding(field_path="provenance", value_type="string")


def test_additive_m2a_architecture_checks():
    assert check(Path(__file__).resolve().parents[1])["pass"]


def test_architecture_guard_rejects_frontend_authority(tmp_path):
    root = Path(__file__).resolve().parents[1]
    paths = [
        "src/crossborder_compliance/application/intake_services.py",
        "src/crossborder_compliance/infrastructure/persistence/project_intake.py",
        "src/crossborder_compliance/infrastructure/intake_composition.py",
        "src/crossborder_compliance/infrastructure/persistence/structured_intake.py",
        "src/crossborder_compliance/interfaces/api/routes/workflow.py",
        "src/crossborder_compliance/application/workflow_formal.py",
        "frontend/src/features/intake/persistence.ts",
    ]
    for path in paths:
        dst = tmp_path / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((root / path).read_bytes())
    path = tmp_path / paths[-1]
    path.write_text(path.read_text() + '\nconst unauthorized = { tenant_id: "client" };\n')
    assert not check(tmp_path)["checks"]["frontend_does_not_authorize"]


def test_m2a_owner_is_finite_and_committed():
    from scripts.m2a_ownership import SHARED, overlay

    root = Path(__file__).resolve().parents[1]
    assert "src/crossborder_compliance/domain/decision_engine.py" not in SHARED
    assert "src/crossborder_compliance/workflows/canonical.py" not in SHARED
    valid, paths, source = overlay(root)
    assert valid and paths and source


def test_m2a_cannot_reassign_unverified_baseline(monkeypatch):
    from scripts import m2a_ownership as ownership

    original = ownership.json.loads

    def changed_record(value):
        data = original(value)
        if isinstance(data, dict) and "source_sha" in data and "paths" in data:
            data["base_sha"] = "unverified"
        return data

    monkeypatch.setattr(ownership.json, "loads", changed_record)
    assert not ownership.overlay(Path(__file__).resolve().parents[1])[0]

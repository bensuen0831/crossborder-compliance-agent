"""Capacity diagnostics retain causal state without leaking storage credentials."""

from uuid import uuid4
from scripts.kb01.diagnose_ci import storage_log_summary, topology_summary, upload_summary


def test_storage_topology_projection_excludes_network_and_identity_fields():
    result = topology_summary({"Topology": {"Max": 40, "Free": 0, "DataCenters": [{"private": "not public"}], "Layouts": [], "credentials": "never expose"}})
    assert result == {"max_volume_slots": 40, "free_volume_slots": 0, "data_centers": 1, "collection_layouts": 0}


def test_storage_log_reports_causal_markers_without_signed_urls_or_keys():
    result = storage_log_summary(b"no free volumes! https://storage.example/object?signature=private raw-key-value\nNo writable volumes\nno space left")
    assert result["no_free_volume"] == result["no_writable_volume"] == result["disk_full"] == 1
    assert "private" not in str(result) and "raw-key-value" not in str(result)


def test_upload_diagnostic_preserves_only_exact_safe_state_and_frozen_budget():
    identity = str(uuid4())
    result = upload_summary({"upload_session_id": identity, "status": "QUARANTINED", "declared_format": "RAR", "declared_bytes": 1080014006, "attempts": 1, "error_code": "SCANNER_RESOURCE_LIMIT", "policy_json": {"scanner_memory_bytes": 4294967296, "provider_secret": "never expose"}, "relative_path": "sensitive name"})
    assert result["upload_session_id"] == identity and result["scanner_memory_bytes"] == 4294967296
    assert result["error_code"] == "SCANNER_RESOURCE_LIMIT"
    assert "never expose" not in str(result) and "sensitive name" not in str(result)


def test_upload_diagnostic_redacts_untrusted_error_detail():
    result = upload_summary({"upload_session_id": "not-a-uuid", "status": "FAILED", "declared_format": "ZIP", "declared_bytes": 1, "attempts": 1, "error_code": "https://secret.example/key?token=private", "policy_json": {"scanner_memory_bytes": "private"}})
    assert result["upload_session_id"] == "REDACTED_INVALID_IDENTITY"
    assert result["error_code"] == "REDACTED_UNSAFE_ERROR_DETAIL"
    assert "private" not in str(result)
    assert result["scanner_memory_bytes"] == "INVALID_BOUNDED_BUDGET"

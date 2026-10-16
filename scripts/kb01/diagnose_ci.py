"""Read-only, bounded CI capacity diagnostics without credentials or raw payloads."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


def topology_summary(payload):
    topology = payload["Topology"]
    return {
        "max_volume_slots": int(topology["Max"]),
        "free_volume_slots": int(topology["Free"]),
        "data_centers": len(topology.get("DataCenters", [])),
        "collection_layouts": len(topology.get("Layouts", [])),
    }


def storage_log_summary(raw):
    # Do not copy URLs, keys, object names or complete server exception text.
    text = raw[-1024 * 1024 :].decode(errors="replace")
    patterns = {
        "no_free_volume": r"no free volumes?",
        "no_writable_volume": r"no writable volumes?",
        "disk_full": r"no space left|disk full",
        "resource_exhausted": r"resource.?exhausted|no more.*volumes?",
        "volume_limit": r"volume.*limit|maximum.*volume",
    }
    return {name: len(re.findall(pattern, text, re.IGNORECASE)) for name, pattern in patterns.items()}


def upload_summary(row):
    try:
        identity = str(UUID(str(row["upload_session_id"])))
    except ValueError:
        identity = "REDACTED_INVALID_IDENTITY"
    code = row.get("error_code")
    if code is not None and not re.fullmatch(r"[A-Z0-9_:-]{1,80}", code):
        code = "REDACTED_UNSAFE_ERROR_DETAIL"
    budget = row["policy_json"].get("scanner_memory_bytes", 2 * 1024**3)
    if not isinstance(budget, int) or isinstance(budget, bool) or not 256 * 1024**2 <= budget <= 8 * 1024**3:
        budget = "INVALID_BOUNDED_BUDGET"
    return {
        "upload_session_id": identity,
        "status": row["status"] if row["status"] in {"CREATING", "UPLOADING", "FINALIZING", "QUEUED_SCAN", "SCANNING", "VERIFIED", "QUARANTINED", "FAILED", "CANCELLING", "CANCELLED", "EXPIRED"} else "UNKNOWN",
        "format": row["declared_format"] if row["declared_format"] in {"DOC", "DOCX", "HTML", "PDF", "TXT", "XHTML", "RAR", "ZIP", "CSV", "XLSX"} else "UNKNOWN",
        "declared_bytes": int(row["declared_bytes"]),
        "attempts": int(row["attempts"]),
        "error_code": code,
        "scanner_memory_bytes": budget,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--services-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--master-port", type=int, default=19333, choices=range(1024, 65536))
    args = parser.parse_args()
    if os.environ.get("KB01_LOCAL_UAT") != "1":
        raise RuntimeError("KB01_DIAGNOSTICS_REQUIRE_EXPLICIT_SYNTHETIC_UAT")
    result = {
        "source_class": "SYNTHETIC_CI_CAPACITY_DIAGNOSTIC",
        "runner_checkout_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "disk": {},
    }
    for label, path in [("workspace", Path.cwd()), ("services", args.services_root)]:
        space = shutil.disk_usage(path)
        result["disk"][label] = {"total_bytes": space.total, "free_bytes": space.free}
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{args.master_port}/dir/status", timeout=3) as response:
            result["storage_topology"] = topology_summary(json.load(response))
    except Exception as error:
        result["storage_topology_error_type"] = type(error).__name__
    log = args.services_root / "s3.log"
    if log.exists():
        with log.open("rb") as source:
            source.seek(max(0, log.stat().st_size - 1024 * 1024))
            result["storage_error_markers"] = storage_log_summary(source.read())
        digest = hashlib.sha256()
        with log.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        result["private_storage_log_sha256"] = digest.hexdigest()
    try:
        from sqlalchemy import create_engine, func, select
        from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import KnowledgeUploadSessionEntity as Upload

        engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3})
        with engine.connect() as connection:
            result["upload_total"] = connection.scalar(select(func.count()).select_from(Upload))
            result["uploads"] = [upload_summary(row) for row in connection.execute(select(
                Upload.upload_session_id, Upload.status, Upload.declared_format, Upload.declared_bytes,
                Upload.attempts, Upload.error_code, Upload.policy_json,
            ).order_by(Upload.created_at.desc()).limit(250)).mappings()]
        engine.dispose()
    except Exception as error:
        result["upload_diagnostic_error_type"] = type(error).__name__
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("Safe read-only synthetic CI capacity diagnostics recorded.")


if __name__ == "__main__":
    main()

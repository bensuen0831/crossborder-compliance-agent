"""Archive orchestration through the same offline process sandbox as the scanner."""

import hashlib
import json
import shutil
from pathlib import Path


class IsolatedKnowledgeArchiveExtractor:
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def extract(self, source: Path, destination: Path, policy):
        destination.mkdir(parents=True, exist_ok=False)
        physical_budget = shutil.disk_usage(destination).free - 2 * 1024**3
        if physical_budget <= 0:
            raise ValueError("KNOWLEDGE_PROCESS_DISK_BUDGET_EXHAUSTED")
        result = self.sandbox.run(
            "/usr/bin/python3",
            [
                "/opt/knowledge-src/crossborder_compliance/infrastructure/knowledge_archive_process.py",
                "--source",
                "/input/original",
                "--destination",
                "/output",
                "--max-bytes",
                str(min(policy.max_expanded_bytes, physical_budget)),
                "--max-entries",
                str(policy.max_archive_entries),
                "--max-file-bytes",
                str(policy.max_single_bytes),
            ],
            {"/input/original": source},
            policy.extraction_timeout_seconds,
            output_directory=destination,
        )
        if result["exit_code"] != 0:
            raise ValueError("ARCHIVE_EXTRACTION_REFUSED")
        summary = json.loads(result["stdout"])
        manifest = destination / ".kb01-extracted-manifest.jsonl"
        digest = hashlib.sha256()
        count, total = 0, 0
        with manifest.open("rb") as records:
            for line in records:
                if len(line) > 8192:
                    raise ValueError("ARCHIVE_MANIFEST_RECORD_LIMIT")
                digest.update(line)
                row = json.loads(line)
                count += 1
                total += row["byte_size"]
        if (
            digest.hexdigest() != summary["manifest_sha256"]
            or count != summary["files"]
            or total != summary["expanded_bytes"]
        ):
            raise ValueError("ARCHIVE_MANIFEST_INTEGRITY_FAILED")
        return {**summary, "image_id": result["image_id"], "manifest_path": manifest}

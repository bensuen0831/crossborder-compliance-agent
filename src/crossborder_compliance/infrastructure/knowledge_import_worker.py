"""Offline extraction and resumable streaming child uploads for durable import work."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from botocore.exceptions import BotoCoreError, ClientError

from crossborder_compliance.domain.knowledge_management import KnowledgeManagementPolicy
from crossborder_compliance.domain.knowledge_upload import (
    DOCUMENT_FORMATS,
    KnowledgeUploadMutation,
    KnowledgeUploadPartReceipt,
    KnowledgeUploadPartRequest,
    StartKnowledgeUpload,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
)


def part_chunks(source, count):
    """Yield exactly one part with bounded memory, even for a 5GiB configured part."""
    while count:
        chunk = source.read(min(8 * 1024**2, count))
        if not chunk:
            raise ValueError("BINARY_VERIFICATION_FAILED")
        count -= len(chunk)
        yield chunk


class KnowledgeImportWorker:
    def __init__(self, batches, uploads, storage, extractor, working_root: Path):
        self.batches, self.uploads, self.storage = batches, uploads, storage
        self.extractor, self.working_root = extractor, working_root.resolve()
        self.working_root.mkdir(parents=True, exist_ok=True)

    def _transfer(self, batch, record, path):
        suffix = path.suffix[1:].upper()
        if suffix not in DOCUMENT_FORMATS:
            raise ValueError("UNSUPPORTED_ARCHIVE_MEMBER_FORMAT")
        identity_key = (
            "batch-child:"
            + batch["batch_id"]
            + ":"
            + hashlib.sha256(record["relative_path"].encode()).hexdigest()[:40]
        )
        row = self.uploads.start(
            StartKnowledgeUpload(
                relative_path=record["relative_path"],
                declared_format=suffix,
                declared_bytes=record["byte_size"],
                content_sha256=record["content_sha256"],
                idempotency_key=identity_key,
            )
        )
        identity = row["upload_session_id"]
        if row["status"] == "UPLOADING":
            received = {part["part_number"]: part for part in row["received_parts"]}
            with path.open("rb") as source:
                for number in range(1, row["part_count"] + 1):
                    self.batches.heartbeat(batch["batch_id"], batch["lease_token"])
                    size = min(row["part_bytes"], record["byte_size"] - source.tell())
                    offset = source.tell()
                    digest = hashlib.sha256()
                    for content in part_chunks(source, size):
                        digest.update(content)
                    sha = digest.hexdigest()
                    if number in received:
                        if (
                            received[number]["content_sha256"] != sha
                            or received[number]["byte_size"] != size
                        ):
                            raise ValueError("BINARY_VERIFICATION_FAILED")
                        continue
                    source.seek(offset)
                    signed = self.uploads.part_url(
                        identity, KnowledgeUploadPartRequest(part_number=number, content_sha256=sha)
                    )
                    local = urlsplit(signed["url"]).hostname in {"127.0.0.1", "localhost", "::1"}
                    with httpx.Client(trust_env=not local, timeout=240) as client:
                        response = client.put(
                            signed["url"],
                            content=part_chunks(source, size),
                            headers={**signed["headers"], "Content-Length": str(size)},
                        )
                        response.raise_for_status()
                    self.uploads.acknowledge(
                        identity,
                        KnowledgeUploadPartReceipt(
                            expected_record_version=row["record_version"],
                            idempotency_key=identity_key + ":" + str(number),
                            part_number=number,
                            content_sha256=sha,
                        ),
                    )
                    row = self.uploads.repository.detail(identity)
        if row["status"] in {"UPLOADING", "FINALIZING"}:
            self.uploads.complete(
                identity,
                KnowledgeUploadMutation(
                    expected_record_version=row["record_version"]
                    - (1 if row["status"] == "FINALIZING" else 0),
                    idempotency_key=identity_key + ":complete",
                ),
            )
        self.batches.extracted_item(batch["batch_id"], batch["lease_token"], identity, record)

    def run_once(self):
        batch = self.batches.extraction_claim()
        if batch is None:
            return False
        digest, count, error = None, 0, None
        archive = batch["archive"]
        try:
            reserve = archive["declared_bytes"] + 2 * 1024**3
            if shutil.disk_usage(self.working_root).free <= reserve:
                raise ValueError("KNOWLEDGE_PROCESS_DISK_BUDGET_EXHAUSTED")
            with tempfile.TemporaryDirectory(prefix="import-", dir=self.working_root) as directory:
                directory = Path(directory)
                directory.chmod(0o755)
                original = directory / "original"
                measured = self.storage.download(
                    archive["object_key"],
                    archive["object_version"],
                    original,
                    archive["declared_bytes"],
                )
                if (
                    measured["byte_size"] != archive["declared_bytes"]
                    or measured["content_sha256"] != archive["content_sha256"]
                ):
                    raise ValueError("BINARY_VERIFICATION_FAILED")
                original.chmod(0o644)
                summary = self.extractor.extract(
                    original,
                    directory / "extracted",
                    KnowledgeManagementPolicy.model_validate(archive["policy"]),
                )
                digest, count = summary["manifest_sha256"], summary["files"]
                # A bounded manifest on disk, not an in-memory archive or source payload.
                with summary["manifest_path"].open("rb") as records:
                    for line in records:
                        record = json.loads(line)
                        self._transfer(
                            batch, record, directory / "extracted" / record["relative_path"]
                        )
        except (BotoCoreError, ClientError, httpx.HTTPError):
            error = "IMPORT_TRANSPORT_UNAVAILABLE"
        except KnowledgeManagementConflict as exc:
            if str(exc) == "KNOWLEDGE_BATCH_LEASE_LOST":
                return True  # Cancellation or another owner won; never overwrite it.
            error = "ARCHIVE_EXTRACTION_REFUSED"
        except (ValueError, TimeoutError) as exc:
            code = str(exc)
            error = (
                code
                if code
                in {
                    "UNSUPPORTED_ARCHIVE_MEMBER_FORMAT",
                    "KNOWLEDGE_PROCESS_DISK_BUDGET_EXHAUSTED",
                    "BINARY_VERIFICATION_FAILED",
                }
                else "ARCHIVE_EXTRACTION_REFUSED"
            )
        self.batches.extraction_finished(
            batch["batch_id"], batch["lease_token"], digest, count, error
        )
        return True

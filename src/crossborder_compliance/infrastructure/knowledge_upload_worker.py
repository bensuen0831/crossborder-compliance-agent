"""Durable PostgreSQL leases and bounded binary verification, outside WorkflowRuntime."""

import hashlib
import shutil
import tempfile
from pathlib import Path


def verify_received_parts(path, receipts):
    with path.open("rb") as source:
        for receipt in receipts:
            remaining = receipt["byte_size"]
            digest = hashlib.sha256()
            while remaining:
                chunk = source.read(min(8 * 1024**2, remaining))
                if not chunk:
                    raise ValueError("BINARY_VERIFICATION_FAILED")
                digest.update(chunk)
                remaining -= len(chunk)
            if digest.hexdigest() != receipt["content_sha256"]:
                raise ValueError("BINARY_VERIFICATION_FAILED")
        if source.read(1):
            raise ValueError("BINARY_VERIFICATION_FAILED")


def verify_binary_container(path, declared_format, sandbox, timeout):
    with path.open("rb") as source:
        header = source.read(8192)
    signatures = {
        "DOC": (bytes.fromhex("d0cf11e0a1b11ae1"),),
        "PDF": (b"%PDF-",),
        "ZIP": (b"PK\x03\x04", b"PK\x05\x06"),
        "RAR": (b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00"),
        "DOCX": (b"PK\x03\x04",),
        "XLSX": (b"PK\x03\x04",),
    }
    if declared_format in signatures:
        if not header.startswith(signatures[declared_format]):
            raise ValueError("UNSUPPORTED_BINARY_FORMAT")
        if declared_format in {"DOCX", "XLSX"}:
            listing = sandbox.run(
                "/usr/bin/bsdtar", ["-tf", "/input/original"], {"/input/original": path}, timeout
            )
            members = set(listing["stdout"].splitlines())
            required = {
                "[Content_Types].xml",
                "word/document.xml" if declared_format == "DOCX" else "xl/workbook.xml",
            }
            if listing["exit_code"] != 0 or not required <= members:
                raise ValueError("UNSUPPORTED_BINARY_FORMAT")
        return declared_format
    encoding = "utf-16" if header.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    import codecs

    text = codecs.getincrementaldecoder(encoding)(errors="strict").decode(header, final=False)
    if "\0" in text:
        raise ValueError("UNSUPPORTED_BINARY_FORMAT")
    if declared_format in {"HTML", "XHTML"}:
        value = text.lstrip().lower()
        if not any(x in value for x in ("<html", "<!doctype html")):
            raise ValueError("UNSUPPORTED_BINARY_FORMAT")
    return declared_format


class KnowledgeUploadWorker:
    def __init__(self, repository, storage, scanner, sandbox, working_root: Path):
        self.repository, self.storage = repository, storage
        self.scanner, self.sandbox = scanner, sandbox
        self.working_root = working_root.resolve()
        self.working_root.mkdir(parents=True, exist_ok=True)

    def run_once(self):
        row = self.repository.scan_claim()
        if row is None:
            return False
        scan = {}
        error = None
        try:
            if shutil.disk_usage(self.working_root).free < row["declared_bytes"] + 256 * 1024**2:
                raise ValueError("BINARY_VERIFICATION_FAILED")
            with tempfile.TemporaryDirectory(prefix="verify-", dir=self.working_root) as directory:
                # Containerized unprivileged tools need traversal through their private input dir.
                Path(directory).chmod(0o755)
                path = Path(directory) / "original"
                measured = self.storage.download(
                    row["object_key"], row["object_version"], path, row["declared_bytes"]
                )
                path.chmod(0o644)
                if (
                    measured["byte_size"] != row["declared_bytes"]
                    or measured["content_sha256"] != row["content_sha256"]
                ):
                    raise ValueError("BINARY_VERIFICATION_FAILED")
                verify_received_parts(
                    path, self.repository.verification_parts(row["upload_session_id"])
                )
                manifest = (
                    row["policy"].get("manifest")
                    if row["declared_format"] in {"CSV", "XLSX"}
                    else None
                )
                result = self.scanner.scan(
                    path,
                    row["policy"]["scanner_timeout_seconds"],
                    memory_bytes=row["policy"].get("scanner_memory_bytes", 2 * 1024**3),
                    max_expanded_bytes=min(
                        row["policy"]["max_expanded_bytes"], manifest["max_expanded_bytes"]
                    )
                    if manifest
                    else row["policy"]["max_expanded_bytes"],
                    max_entries=min(row["policy"]["max_archive_entries"], manifest["max_entries"])
                    if manifest
                    else row["policy"]["max_archive_entries"],
                )
                if type(result.get("clean")) is not bool:
                    raise ValueError("SCANNER_UNAVAILABLE")
                scan = {"bucket": self.storage.bucket, **measured, "scanner": result}
                if not result["clean"]:
                    error = "MALWARE_DETECTED"
                else:
                    scan["detected_format"] = verify_binary_container(
                        path,
                        row["declared_format"],
                        self.sandbox,
                        row["policy"]["extraction_timeout_seconds"],
                    )
        except TimeoutError:
            error = "SCANNER_TIMEOUT"
        except ValueError as exc:
            code = str(exc)
            error = (
                code
                if code
                in {
                    "MALWARE_DETECTED",
                    "BINARY_VERIFICATION_FAILED",
                    "SCANNER_UNAVAILABLE",
                    "UNSUPPORTED_BINARY_FORMAT",
                    "SCANNER_LIMIT_EXCEEDED",
                    "ENCRYPTED_BINARY_UNSUPPORTED",
                }
                else "SCANNER_UNAVAILABLE"
            )
        except Exception:
            error = "BINARY_VERIFICATION_FAILED"
        self.repository.scan_result(row["upload_session_id"], row["lease_token"], scan, error)
        return True

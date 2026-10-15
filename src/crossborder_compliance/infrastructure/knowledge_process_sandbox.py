"""Bounded offline processes, using an explicitly configured immutable local image."""

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4


class KnowledgeProcessSandbox:
    EXECUTABLES = frozenset({"/usr/bin/bsdtar", "/usr/bin/clamscan", "/usr/bin/python3.13"})

    def __init__(self, image_id: str, working_root: Path):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise ValueError("IMMUTABLE_KNOWLEDGE_TOOL_IMAGE_REQUIRED")
        self.image_id = image_id
        self.working_root = working_root.resolve()
        self.working_root.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        executable,
        args,
        mounts,
        timeout,
        *,
        memory_bytes=2 * 1024**3,
        output_directory=None,
        scratch_bytes=None,
    ):
        if executable not in self.EXECUTABLES or not 1 <= timeout <= 14400:
            raise ValueError("KNOWLEDGE_PROCESS_NOT_ALLOWED")
        if any(not isinstance(a, str) or "\0" in a for a in args):
            raise ValueError("INVALID_KNOWLEDGE_PROCESS_ARGUMENT")
        if scratch_bytes is not None and not 0 < scratch_bytes <= 50 * 1024**3:
            raise ValueError("INVALID_KNOWLEDGE_SCRATCH_BUDGET")
        name = "kb01-process-" + uuid4().hex
        uid = os.getuid()
        if uid == 0:
            uid = 65534
        command = [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            name,
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            "--memory=" + str(memory_bytes),
            "--cpus=2",
            "--user=" + str(uid),
            "--entrypoint=" + executable,
        ]
        for destination, source in mounts.items():
            source = Path(source)
            if (
                source.is_symlink()
                or not source.resolve().is_relative_to(self.working_root)
                or "," in str(source)
                or not re.fullmatch(r"/(input|database)/[a-zA-Z0-9_.-]+", destination)
            ):
                raise ValueError("KNOWLEDGE_PROCESS_MOUNT_NOT_ALLOWED")
            command += ["--mount", f"type=bind,src={source.resolve()},dst={destination},readonly"]
        if output_directory is not None:
            output = Path(output_directory)
            if (
                not output.is_dir()
                or output.is_symlink()
                or "," in str(output)
                or not output.resolve().is_relative_to(self.working_root)
            ):
                raise ValueError("KNOWLEDGE_PROCESS_OUTPUT_NOT_ALLOWED")
            command += ["--mount", f"type=bind,src={output.resolve()},dst=/output"]
        with tempfile.TemporaryDirectory(dir=self.working_root) as directory:
            scratch = None
            if scratch_bytes is None:
                command += ["--tmpfs=/tmp:rw,nosuid,nodev,size=134217728"]
            else:
                # Large archive scanners materialize members. A bounded owned disk
                # scratch avoids a 128MiB tmpfs failure without enlarging RAM limits.
                scratch = Path(directory) / "scratch"
                scratch.mkdir(mode=0o700)
                command += ["--mount", f"type=bind,src={scratch},dst=/tmp"]
            command += [self.image_id, *args]
            # On-disk diagnostics are bounded; untrusted output never becomes a giant buffer.
            stdout, stderr = Path(directory) / "out", Path(directory) / "err"
            with stdout.open("wb") as out, stderr.open("wb") as err:
                process = subprocess.Popen(command, stdout=out, stderr=err)
                try:
                    deadline = time.monotonic() + timeout
                    while process.poll() is None:
                        if (
                            output_directory is not None or scratch is not None
                        ) and shutil.disk_usage(self.working_root).free < 1024**3:
                            raise ValueError("KNOWLEDGE_PROCESS_DISK_BUDGET_EXHAUSTED")
                        if scratch is not None:
                            total, files = 0, 0
                            for parent, _, names in os.walk(scratch, followlinks=False):
                                for filename in names:
                                    try:
                                        total += (Path(parent) / filename).lstat().st_size
                                    except FileNotFoundError:
                                        continue  # The scanner deleted its temporary file.
                                    files += 1
                                    if total > scratch_bytes or files > 50000:
                                        raise ValueError("KNOWLEDGE_PROCESS_SCRATCH_LIMIT")
                        if stdout.stat().st_size + stderr.stat().st_size > 8 * 1024**2:
                            raise ValueError("KNOWLEDGE_PROCESS_OUTPUT_LIMIT")
                        if time.monotonic() >= deadline:
                            raise TimeoutError("KNOWLEDGE_PROCESS_TIMEOUT")
                        time.sleep(0.1)
                    code = process.returncode
                except (TimeoutError, ValueError):
                    subprocess.run(
                        ["docker", "rm", "--force", name], capture_output=True, timeout=15
                    )
                    process.kill()
                    process.wait()
                    raise
            if stdout.stat().st_size + stderr.stat().st_size > 8 * 1024**2:
                raise ValueError("KNOWLEDGE_PROCESS_OUTPUT_LIMIT")
            return {
                "exit_code": code,
                "stdout": stdout.read_text(errors="replace"),
                "stderr": stderr.read_text(errors="replace"),
                "image_id": self.image_id,
            }


class ClamKnowledgeScanner:
    """Offline ClamAV with a configured database, never a 'clean' stub."""

    def __init__(self, sandbox: KnowledgeProcessSandbox, database: Path, database_identity: str):
        self.sandbox, self.database = sandbox, database
        self.database_identity = database_identity

    def scan(self, path, timeout, *, max_expanded_bytes=50 * 1024**3, max_entries=20000):
        if not self.database.is_dir() or not any(self.database.iterdir()):
            raise ValueError("SCANNER_DATABASE_NOT_CONFIGURED")
        result = self.sandbox.run(
            "/usr/bin/clamscan",
            [
                "--database=/database/signatures",
                "--no-summary",
                "--stdout",
                "--alert-exceeds-max=yes",
                "--alert-encrypted=yes",
                "--max-scantime=" + str(timeout * 1000),
                "--max-filesize=" + str(path.stat().st_size + 1),
                "--max-scansize=" + str(max_expanded_bytes),
                "--max-files=" + str(max_entries),
                "/input/original",
            ],
            {"/database/signatures": self.database, "/input/original": path},
            timeout,
            scratch_bytes=min(
                max_expanded_bytes,
                max(1, shutil.disk_usage(self.sandbox.working_root).free - 2 * 1024**3),
            ),
        )
        if result["exit_code"] not in {0, 1}:
            raise ValueError("SCANNER_UNAVAILABLE")
        if "Heuristics.Limits.Exceeded" in result["stdout"]:
            raise ValueError("SCANNER_LIMIT_EXCEEDED")
        if "Heuristics.Encrypted" in result["stdout"]:
            raise ValueError("ENCRYPTED_BINARY_UNSUPPORTED")
        # No raw document, provider payload, pathname or diagnostic is audited.
        return {
            "clean": result["exit_code"] == 0,
            "engine": "CLAMAV",
            "database_identity": self.database_identity,
            "image_id": result["image_id"],
        }

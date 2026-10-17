"""Build only the audited stdlib parser files, not the repository or credentials."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "domain/document_text.py",
    "domain/knowledge_paths.py",
    "infrastructure/native_document_extraction.py",
    "infrastructure/knowledge_native_process.py",
    "infrastructure/knowledge_archive_process.py",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag", default="kb01-acceptance-tools:local")
    args = parser.parse_args()
    # Preserve Docker client configuration, proxy and CA trust. Never print env.
    with tempfile.TemporaryDirectory(prefix="kb01-tools-") as scratch:
        context = Path(scratch)
        shutil.copyfile(ROOT / "scripts/kb01/Containerfile", context / "Dockerfile")
        package = context / "crossborder_compliance"
        for name in ("", "domain", "infrastructure"):
            directory = package / name
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "__init__.py").touch()
        digests = {}
        for relative in SOURCES:
            source = ROOT / "src/crossborder_compliance" / relative
            shutil.copyfile(source, package / relative)
            digests[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
        command = ["docker", "build", "--tag", args.tag]
        ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
        if ca and Path(ca).is_file():
            command += ["--secret", f"id=system_ca,src={ca}"]
        command += [str(context)]
        subprocess.run(command, check=True)
        identity = subprocess.check_output(
            ["docker", "image", "inspect", "--format", "{{.Id}}", args.tag], text=True
        ).strip()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "image_id": identity,
                    "source_sha256": digests,
                    "containerfile_sha256": hashlib.sha256(
                        (ROOT / "scripts/kb01/Containerfile").read_bytes()
                    ).hexdigest(),
                },
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()

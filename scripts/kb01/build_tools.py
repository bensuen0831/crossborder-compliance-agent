"""Build only the audited stdlib parser files, not the repository or credentials."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
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
        shutil.copyfile(ROOT / "scripts/kb01/image_inventory.py", context / "image_inventory.py")
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
        if not ca and Path("/etc/ssl/certs/ca-certificates.crt").is_file():
            ca = "/etc/ssl/certs/ca-certificates.crt"
        if ca and Path(ca).is_file():
            command += ["--secret", f"id=system_ca,src={ca}"]
        command += [str(context)]
        subprocess.run(command, check=True)
        identity = subprocess.check_output(
            ["docker", "image", "inspect", "--format", "{{.Id}}", args.tag], text=True
        ).strip()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        identity_evidence = {
            "runner_checkout_sha": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_dirty": bool(
                subprocess.check_output(
                    ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
                ).strip()
            ),
            "image_id": identity,
            "source_sha256": digests,
            "containerfile_sha256": hashlib.sha256(
                (context / "Dockerfile").read_bytes()
            ).hexdigest(),
            "inventory_script_sha256": hashlib.sha256(
                (context / "image_inventory.py").read_bytes()
            ).hexdigest(),
        }
        args.output.write_text(json.dumps(identity_evidence, indent=2) + "\n")
        sys.path.insert(0, str(ROOT))
        from scripts.kb01.toolchain_provenance import collect

        proof = collect(args.output.parent / "toolchain", identity_evidence)
        identity_evidence["oci_manifest_digest"] = proof["oci"]["manifest_digest"]
        identity_evidence["provenance_path"] = str(args.output.parent / "toolchain/provenance.json")
        args.output.write_text(json.dumps(identity_evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()

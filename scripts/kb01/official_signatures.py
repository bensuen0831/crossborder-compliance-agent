"""Verify official ClamAV CVDs for browser acceptance, separately from EICAR fixtures."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

DOWNLOAD = r"""
import os, pathlib, subprocess
from urllib.parse import urlsplit, unquote
config = ["DatabaseDirectory /database", "DatabaseOwner root",
          "DatabaseMirror database.clamav.net", "MaxAttempts 1",
          "ConnectTimeout 30", "ReceiveTimeout 180"]
proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
if proxy:
    parsed = urlsplit(proxy)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ValueError("UNSUPPORTED_TRUSTED_DOWNLOADER_PROXY")
    config += ["HTTPProxyServer " + parsed.hostname,
               "HTTPProxyPort " + str(parsed.port or 80)]
    if parsed.username:
        config += ["HTTPProxyUsername " + unquote(parsed.username),
                   "HTTPProxyPassword " + unquote(parsed.password or "")]
path = pathlib.Path("/tmp/freshclam.conf")
path.write_text("\n".join(config) + "\n")
path.chmod(0o600)
try:
    subprocess.run(["/usr/bin/freshclam", "--config-file=" + str(path)], check=True)
finally:
    path.unlink(missing_ok=True)
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if not args.image.startswith("sha256:") or len(args.image) != 71:
        raise ValueError("IMMUTABLE_SCANNER_IMAGE_REQUIRED")
    database = args.root.resolve()
    database.mkdir(parents=True, exist_ok=True)
    names = ("main.cvd", "daily.cvd", "bytecode.cvd")
    if not all((database / name).is_file() for name in names):
        # Trusted installer only: no original documents, credentials or Docker
        # socket are mounted. The actual untrusted scanner remains offline.
        command = [
            "docker",
            "run",
            "--rm",
            "--user=" + str(os.getuid()),
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--mount",
            f"type=bind,src={database},dst=/database",
        ]
        ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
        if ca and Path(ca).is_file():
            command += [
                "--mount",
                f"type=bind,src={Path(ca).resolve()},dst=/etc/ssl/certs/ca-certificates.crt,readonly",
            ]
        command += ["--entrypoint=/usr/bin/python3", args.image, "-c", DOWNLOAD]
        subprocess.run(command, check=True, timeout=900)
    measured = {}
    for name in names:
        path = database / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("OFFICIAL_CVD_MISSING")
        # sigtool validates the archive signature, not merely its filename/hash.
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--mount",
                f"type=bind,src={database},dst=/database,readonly",
                "--entrypoint=/usr/bin/sigtool",
                args.image,
                "--info",
                "/database/" + name,
            ],
            check=True,
            timeout=120,
        )
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        measured[name] = {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(
        json.dumps(
            {
                "database_identity": "OFFICIAL_CLAMAV_VERIFIED_CVD_MAIN_DAILY_BYTECODE",
                "image_id": args.image,
                "signature_verification": "PASS",
                "files": measured,
                "limitation": (
                    "Official antivirus signatures are not real-regulatory legal acceptance"
                ),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

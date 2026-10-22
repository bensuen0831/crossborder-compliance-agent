"""Ephemeral loopback versioned S3 and explicitly synthetic antivirus fixtures.

Outputs only private configuration paths and immutable tool identities. This is
technical test setup, not official-signature or real-regulatory acceptance.
"""

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

from crossborder_compliance.infrastructure.knowledge_binary_storage import S3KnowledgeBinaryStore

WEED_URL = "https://github.com/seaweedfs/seaweedfs/releases/download/4.48/linux_amd64.tar.gz"
WEED_SHA256 = "4a7d108384d044d95212d1342cdda9533fa55842c1c9b41f606ca3c8a9561124"


def private_json(path, value):
    with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as output:
        json.dump(value, output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--tool-evidence", type=Path, required=True)
    parser.add_argument("--port-offset", type=int, default=0, choices=range(0, 1001))
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Restart only this retained isolated S3 data directory",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=args.resume)
    tool = json.loads(args.tool_evidence.read_text())
    image = tool["image_id"]
    if not image.startswith("sha256:") or len(image) != 71:
        raise ValueError("IMMUTABLE_KB01_TOOL_IMAGE_REQUIRED")
    archive = root / "seaweedfs.tar.gz"
    if not archive.exists():
        with (
            urllib.request.urlopen(WEED_URL, timeout=120) as response,
            archive.open("xb") as output,
        ):
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    digest = hashlib.sha256()
    with archive.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != WEED_SHA256:
        raise ValueError("SEAWEEDFS_RELEASE_DIGEST_MISMATCH")
    executable = root / "weed"
    with tarfile.open(archive) as bundle:
        members = [
            member
            for member in bundle.getmembers()
            if member.name in {"weed", "./weed"} and member.isfile()
        ]
        if len(members) != 1:
            raise ValueError("SEAWEEDFS_RELEASE_MEMBER_MISMATCH")
        source = bundle.extractfile(members[0])
        assert source is not None
        expected_executable = hashlib.sha256()
        if executable.exists():
            while chunk := source.read(1024 * 1024):
                expected_executable.update(chunk)
            if hashlib.sha256(executable.read_bytes()).digest() != expected_executable.digest():
                raise ValueError("SEAWEEDFS_EXECUTABLE_DIGEST_MISMATCH")
        else:
            with executable.open("xb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
    executable.chmod(0o700)
    if not args.resume:
        access, secret = secrets.token_hex(16), secrets.token_hex(32)
        private_json(
            root / "identities.json",
            {
                "identities": [
                    {
                        "name": "kb01-ci",
                        "credentials": [{"accessKey": access, "secretKey": secret}],
                        "actions": ["Admin", "Read", "Write", "List", "Tagging"],
                    }
                ]
            },
        )
    else:
        saved = json.loads((root / "client.json").read_text())
        access, secret = saved["access_key"], saved["secret_key"]
    data = root / "data"
    data.mkdir(exist_ok=args.resume)
    with (root / "s3.log").open("ab") as log:
        process = subprocess.Popen(
            [
                str(executable),
                "server",
                f"-dir={data}",
                "-ip=127.0.0.1",
                "-ip.bind=127.0.0.1",
                f"-master.port={19333 + args.port_offset}",
                "-master.volumeSizeLimitMB=1024",
                f"-volume.port={18080 + args.port_offset}",
                f"-filer.port={18888 + args.port_offset}",
                "-s3",
                "-s3.port.lance=0",
                "-s3.port.iceberg=0",
                f"-s3.port={19000 + args.port_offset}",
                f"-s3.config={root / 'identities.json'}",
                "-volume.max=40",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    (root / "process.json").write_text(
        json.dumps({"pid": process.pid, "executable": str(executable)})
    )
    config = {
        "endpoint_url": f"http://127.0.0.1:{19000 + args.port_offset}",
        "bucket": "kb01-acceptance",
        "access_key": access,
        "secret_key": secret,
    }
    if not args.resume:
        private_json(root / "client.json", config)
    store = S3KnowledgeBinaryStore(**config)
    for attempt in range(60):
        if process.poll() is not None:
            raise RuntimeError("KB01_LOCAL_S3_EXITED")
        try:
            store.client.list_buckets()
            break
        except Exception:
            if attempt == 59:
                raise RuntimeError("KB01_LOCAL_S3_NOT_READY") from None
            time.sleep(1)
    # A writable S3 port is not proof that the bounded volume pool registered.
    for attempt in range(60):
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{19333 + args.port_offset}/dir/status", timeout=3
            ) as response:
                topology = json.load(response)["Topology"]
            if topology["Max"] == 40:
                break
        except Exception:
            pass
        if attempt == 59:
            raise RuntimeError("KB01_LOCAL_S3_VOLUME_CAPACITY_NOT_READY")
        time.sleep(1)
    if not args.resume:
        store.client.create_bucket(Bucket=store.bucket)
    store.client.put_bucket_versioning(
        Bucket=store.bucket, VersioningConfiguration={"Status": "Enabled"}
    )
    assert store.client.get_bucket_versioning(Bucket=store.bucket)["Status"] == "Enabled"
    store.client.put_bucket_cors(
        Bucket=store.bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": [
                        "http://127.0.0.1:15173",
                        "http://localhost:15173",
                        "http://127.0.0.1:15174",
                    ],
                    "AllowedMethods": ["PUT"],
                    "AllowedHeaders": ["content-type", "x-amz-checksum-sha256"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 300,
                }
            ]
        },
    )
    scan, native, archives = root / "scan", root / "native", root / "archive"
    for directory in (scan, native, archives):
        directory.mkdir(exist_ok=args.resume)
    signatures = scan / "synthetic-signatures"
    signatures.mkdir(exist_ok=args.resume)
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    (signatures / "synthetic.ndb").write_text("KB01.EICAR:0:*:" + eicar.hex() + "\n")
    variables = {
        "KB01_TEST_S3_CONFIG": str(root / "client.json"),
        "KB01_TEST_TOOL_IMAGE": image,
        "KB01_TEST_WORK_ROOT": str(scan),
        "KB01_TEST_SCAN_DATABASE": str(signatures),
        "KB01_TEST_ARCHIVE_IMAGE": image,
        "KB01_TEST_ARCHIVE_WORK_ROOT": str(archives),
        "KB01_TEST_NATIVE_IMAGE": image,
        "KB01_TEST_NATIVE_WORK_ROOT": str(native),
    }
    destination = os.environ.get("GITHUB_ENV")
    if destination:
        with Path(destination).open("a") as output:
            for key, value in variables.items():
                if "\n" in value or "\r" in value:
                    raise ValueError("UNSAFE_ENVIRONMENT_PATH")
                output.write(f"{key}={value}\n")
    (root / "service-evidence.json").write_text(
        json.dumps(
            {
                "s3_versioning": "Enabled",
                "bounded_volume_slots": 40,
                "observed_volume_slots": topology["Max"],
                "observed_free_volume_slots": topology["Free"],
                "tool_image": image,
                "scanner_database": "SYNTHETIC_SECURITY_SIGNATURES:EICAR_ONLY",
                "seaweedfs_release_sha256": WEED_SHA256,
                "variables": variables,
            },
            indent=2,
        )
        + "\n"
    )
    print("Versioned local S3 and synthetic security fixture ready; no credentials emitted.")


if __name__ == "__main__":
    main()

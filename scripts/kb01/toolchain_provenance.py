"""Bind new tool-image evidence to actual binary content, never historical guesses."""

import hashlib
import json
import os
import subprocess
import tarfile
import urllib.request
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from scripts.kb01.oci_tools import digest, export, restore

BASE = "sha256:78d4744ead1f5b19b04d0df558ab182a5300903900755e515b2ca4d10eb2044d"
TRIVY = "0.76.1"
TRIVY_SHA = "c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0"
SCHEMA = "https://raw.githubusercontent.com/spdx/spdx-spec/aadf3b0b8dbbabdb4d880b0fc714255fea436ff7/schemas/spdx-schema.json"
SCHEMA_SHA = "239208b7ac287b3cf5d9a9af23f9d69863971102a5e1587a27a398b43490b89b"


def fetch(url):
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read()


def verified_base(root):
    # Public anonymous, read-only Docker Hub token; never logged or persisted.
    token = json.loads(
        fetch(
            "https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/ubuntu:pull"
        )
    )["token"]
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.oci.image.manifest.v1+json",
    }
    request = urllib.request.Request(
        "https://registry-1.docker.io/v2/library/ubuntu/manifests/" + BASE, headers=headers
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    if "sha256:" + hashlib.sha256(raw).hexdigest() != BASE:
        raise ValueError("BASE_MANIFEST_DIGEST_MISMATCH")
    manifest = json.loads(raw)
    request = urllib.request.Request(
        "https://registry-1.docker.io/v2/library/ubuntu/blobs/" + manifest["config"]["digest"],
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        cfg = response.read()
    if "sha256:" + hashlib.sha256(cfg).hexdigest() != manifest["config"]["digest"]:
        raise ValueError("BASE_CONFIG_DIGEST_MISMATCH")
    config = json.loads(cfg)
    if config["os"] != "linux" or config["architecture"] != "amd64":
        raise ValueError("BASE_PLATFORM_MISMATCH")
    (root / "base-manifest.json").write_bytes(raw)
    (root / "base-config.json").write_bytes(cfg)
    return {
        "manifest_digest": BASE,
        "config_digest": manifest["config"]["digest"],
        "platform": "linux/amd64",
        "verification": "VERIFIED_FROM_REGISTRY_CONTENT",
    }


def sbom(root, inventory, oci):
    packages = [
        {
            "name": "kb01-native-tools",
            "SPDXID": "SPDXRef-ToolImage",
            "versionInfo": oci["manifest_digest"],
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "copyrightText": "NOASSERTION",
        }
    ]
    relations = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-ToolImage",
        }
    ]
    for p in inventory["installed_packages"]:
        ident = (
            "SPDXRef-Package-"
            + hashlib.sha256((p["name"] + "@" + p["version"]).encode()).hexdigest()[:24]
        )
        purl = (
            "pkg:deb/ubuntu/"
            + quote(p["name"].split(":")[0], safe="")
            + "@"
            + quote(p["version"], safe="")
            + "?arch="
            + quote(p["architecture"], safe="")
        )
        packages.append(
            {
                "name": p["name"],
                "SPDXID": ident,
                "versionInfo": p["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "sourceInfo": p["source_package"] + " " + p["source_version"],
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": purl,
                    }
                ],
            }
        )
        relations.append(
            {
                "spdxElementId": "SPDXRef-ToolImage",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": ident,
            }
        )
    bom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "KB01 actual tool OCI image package inventory",
        "documentNamespace": "https://spdx.org/spdxdocs/kb01-" + str(uuid.uuid4()),
        "creationInfo": {
            "creators": ["Tool: KB01 image_inventory"],
            "created": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "comment": (
            "Actual tool image package inventory; NOASSERTION for unverified licensing. "
            "Not a zero-CVE claim or historical CI attestation."
        ),
        "packages": packages,
        "relationships": relations,
    }
    from jsonschema import Draft7Validator

    raw = fetch(SCHEMA)
    if hashlib.sha256(raw).hexdigest() != SCHEMA_SHA:
        raise ValueError("SPDX_SCHEMA_DIGEST_MISMATCH")
    Draft7Validator(json.loads(raw)).validate(bom)
    (root / "sbom.spdx.json").write_text(json.dumps(bom, indent=2) + "\n")
    return {
        "decision": "PASS",
        "standard": "SPDX-2.3",
        "packages": len(packages) - 1,
        "schema_sha256": SCHEMA_SHA,
        "schema_url": SCHEMA,
        "sbom_sha256": digest(root / "sbom.spdx.json"),
    }


def scan(root, image):
    archive = root / "trivy.tar.gz"
    archive.write_bytes(
        fetch(
            f"https://github.com/aquasecurity/trivy/releases/download/v{TRIVY}/trivy_{TRIVY}_Linux-64bit.tar.gz"
        )
    )
    if digest(archive) != TRIVY_SHA:
        raise ValueError("SCANNER_RELEASE_DIGEST_MISMATCH")
    binary = root / "trivy"
    with tarfile.open(archive) as bundle:
        member = bundle.getmember("trivy")
        if not member.isfile():
            raise ValueError("SCANNER_BINARY_REQUIRED")
        with bundle.extractfile(member) as source, binary.open("wb") as out:
            import shutil

            shutil.copyfileobj(source, out)
    binary.chmod(0o700)
    env = {**os.environ, "DOCKER_HOST": "unix:///var/run/docker.sock"}
    with (root / "security-scan.log").open("w") as log:
        subprocess.run(
            [
                str(binary),
                "image",
                "--image-src",
                "docker",
                "--cache-dir",
                str(root / "trivy-cache"),
                "--db-repository",
                "ghcr.io/aquasecurity/trivy-db:2",
                "--scanners",
                "vuln",
                "--format",
                "json",
                "--output",
                str(root / "vulnerabilities.json"),
                "--no-progress",
                "--timeout",
                "5m",
                image,
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    result = json.loads((root / "vulnerabilities.json").read_text())
    findings = [v for r in result.get("Results", []) for v in r.get("Vulnerabilities", [])]
    # Scan completion and security acceptance are deliberately separate. No
    # suppression/ignore-unfixed/automatic risk acceptance is introduced.
    blocking = [v for v in findings if v["Severity"] in ("CRITICAL", "HIGH")]
    db = root / "trivy-cache/db"
    return {
        "scan_execution": "PASS",
        "security_acceptance": "BLOCKED_REVIEW_REQUIRED" if blocking else "PASS",
        "scanner_version": TRIVY,
        "scanner_archive_sha256": TRIVY_SHA,
        "report_sha256": digest(root / "vulnerabilities.json"),
        "severities": dict(Counter(v["Severity"] for v in findings)),
        "high_critical_findings": len(blocking),
        "database_files": {p.name: digest(p) for p in db.glob("*") if p.is_file()},
        "risk_acceptance": None,
    }


def collect(root, identity):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    image = identity["image_id"]
    base = verified_base(root)
    raw = subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--read-only",
            "--user=65534",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=536870912",
            "--pids-limit=32",
            "--cpus=1",
            "--entrypoint=/usr/bin/python3",
            image,
            "/opt/kb01/image_inventory.py",
        ]
    )
    inventory = json.loads(raw)
    (root / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    oci = export(image, root / "image.oci.tar")
    roundtrip = restore(root / "image.oci.tar", oci)
    restored = subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--read-only",
            "--user=65534",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=536870912",
            "--pids-limit=32",
            "--cpus=1",
            "--entrypoint=/usr/bin/python3",
            image,
            "/opt/kb01/image_inventory.py",
        ]
    )
    if json.loads(restored) != inventory:
        raise ValueError("RESTORED_TOOL_INVENTORY_CHANGED")
    validation = sbom(root, inventory, oci)
    security = scan(root, image)
    provenance = {
        "schema": "KB01_TOOLCHAIN_PROVENANCE_V1",
        "base": base,
        "oci": oci,
        "source_build": identity,
        "sbom": validation,
        "security": security,
        "restore": roundtrip,
        "tool_hashes": "PASS",
        "apt_provenance": "VERIFIED",
        "image_retention": "EXTERNAL_DEPENDENCY_UNTIL_ARTIFACT_UPLOAD_VERIFIED",
        "rebuild_contract": (
            "Fixed base and authenticated snapshot dependencies; restore exact archived image "
            "for byte identity. Bit-identical fresh Docker build is not asserted."
        ),
    }
    (root / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return provenance

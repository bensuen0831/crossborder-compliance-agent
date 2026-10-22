"""Verified OCI archive export/restore using the existing local Docker daemon.

No registry push, archive extractall, credential handling or untrusted image is
involved. OCI manifest digest and Docker config ID are distinct identities.
"""

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        while chunk := source.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def export(image, archive):
    archive = Path(archive)
    with tempfile.TemporaryDirectory(prefix="kb01-oci-", dir=archive.parent) as tmp:
        root = Path(tmp)
        saved = root / "docker.tar"
        subprocess.run(["docker", "image", "save", "--output", str(saved), image], check=True)
        blobs = root / "oci/blobs/sha256"
        blobs.mkdir(parents=True)
        with tarfile.open(saved) as bundle:
            manifest_file = bundle.extractfile("manifest.json")
            manifest = json.load(manifest_file)
            if len(manifest) != 1:
                raise ValueError("ONE_TOOL_IMAGE_REQUIRED")
            descriptor = manifest[0]
            layers = []
            config = None
            for name in [descriptor["Config"], *descriptor["Layers"]]:
                member = bundle.getmember(name)
                if not member.isfile():
                    raise ValueError("REGULAR_OCI_CONTENT_REQUIRED")
                target = root / "blob"
                with bundle.extractfile(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                h = digest(target)
                size = target.stat().st_size
                target.replace(blobs / h)
                item = {
                    "mediaType": "application/vnd.oci.image.layer.v1.tar",
                    "digest": "sha256:" + h,
                    "size": size,
                }
                if name == descriptor["Config"]:
                    item["mediaType"] = "application/vnd.oci.image.config.v1+json"
                    config = item
                else:
                    layers.append(item)
        if config["digest"] != image:
            raise ValueError("EXPORTED_CONFIG_ID_MISMATCH")
        content = encoded(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": config,
                "layers": layers,
            }
        )
        identity = "sha256:" + hashlib.sha256(content).hexdigest()
        (blobs / identity.split(":")[1]).write_bytes(content)
        layout = root / "oci"
        (layout / "index.json").write_bytes(
            encoded(
                {
                    "schemaVersion": 2,
                    "manifests": [
                        {
                            "mediaType": "application/vnd.oci.image.manifest.v1+json",
                            "digest": identity,
                            "size": len(content),
                            "platform": {"os": "linux", "architecture": "amd64"},
                        }
                    ],
                }
            )
        )
        (layout / "oci-layout").write_bytes(encoded({"imageLayoutVersion": "1.0.0"}))
        # Uncompressed, streaming tar keeps the runtime/restore budget bounded.
        with tarfile.open(archive, "w") as output:
            for path in sorted(layout.rglob("*")):
                if path.is_file():
                    info = output.gettarinfo(path, arcname=str(path.relative_to(layout)))
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ""
                    with path.open("rb") as source:
                        output.addfile(info, source)
    return {
        "format": "OCI_IMAGE_LAYOUT_1.0_ARCHIVE",
        "manifest_digest": identity,
        "config_digest": image,
        "archive_sha256": digest(archive),
        "bytes": archive.stat().st_size,
    }


def restore(archive, expected):
    """Verify every referenced blob before loading equivalent content into Docker."""
    if digest(archive) != expected["archive_sha256"]:
        raise ValueError("OCI_ARCHIVE_DIGEST_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="kb01-restore-", dir=Path(archive).parent) as tmp:
        root = Path(tmp)
        with tarfile.open(archive) as bundle:
            index = json.load(bundle.extractfile("index.json"))
            if len(index["manifests"]) != 1:
                raise ValueError("ONE_OCI_MANIFEST_REQUIRED")
            entry = index["manifests"][0]
            if entry["digest"] != expected["manifest_digest"]:
                raise ValueError("OCI_MANIFEST_IDENTITY_MISMATCH")

            def read_blob(item, destination):
                algorithm, value = item["digest"].split(":")
                if (
                    algorithm != "sha256"
                    or len(value) != 64
                    or any(c not in "0123456789abcdef" for c in value)
                ):
                    raise ValueError("INVALID_OCI_DIGEST")
                member = bundle.getmember("blobs/sha256/" + value)
                if not member.isfile() or member.size != item["size"]:
                    raise ValueError("OCI_BLOB_SIZE_OR_TYPE_MISMATCH")
                with bundle.extractfile(member) as source, destination.open("wb") as out:
                    shutil.copyfileobj(source, out, 1024 * 1024)
                if digest(destination) != value:
                    raise ValueError("OCI_BLOB_DIGEST_MISMATCH")

            mp = root / "manifest"
            read_blob(entry, mp)
            manifest = json.loads(mp.read_text())
            config = manifest["config"]
            if config["digest"] != expected["config_digest"]:
                raise ValueError("OCI_CONFIG_IDENTITY_MISMATCH")
            paths = []
            for n, item in enumerate([config, *manifest["layers"]]):
                path = root / ("config.json" if n == 0 else f"layer-{n}.tar")
                read_blob(item, path)
                paths.append(path)
            docker_manifest = encoded(
                [{"Config": "config.json", "RepoTags": [], "Layers": [p.name for p in paths[1:]]}]
            )
            saved = root / "restore.tar"
            with tarfile.open(saved, "w") as output:
                for path in paths:
                    output.add(path, arcname=path.name)
                info = tarfile.TarInfo("manifest.json")
                info.size = len(docker_manifest)
                output.addfile(info, io.BytesIO(docker_manifest))
            subprocess.run(
                ["docker", "image", "load", "--input", str(saved)],
                check=True,
                stdout=subprocess.DEVNULL,
            )
    return {
        "decision": "PASS",
        "scope": (
            "All OCI blobs verified and content round-tripped into local Docker; "
            "not an independent clean-host or long-term retention claim"
        ),
    }

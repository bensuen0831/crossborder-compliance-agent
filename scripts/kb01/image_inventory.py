"""Stdlib-only image inventory; no credential/environment discovery."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

BINARIES = (
    "/usr/bin/python3.13",
    "/usr/bin/bsdtar",
    "/usr/bin/clamscan",
    "/usr/bin/freshclam",
    "/usr/bin/sigtool",
    "/usr/bin/pdfinfo",
    "/usr/bin/pdftotext",
    "/usr/bin/pdftoppm",
    "/usr/bin/tesseract",
    "/usr/lib/libreoffice/program/oosplash",
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def run(*args):
    return subprocess.check_output(list(args), text=True)


def package_inventory():
    fmt = "${binary:Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}\n"
    fields = ("name", "version", "architecture", "source_package", "source_version")
    return [
        dict(zip(fields, row.split("\t"), strict=True))
        for row in run("dpkg-query", "-W", "-f", fmt).splitlines()
    ]


def apt_build():
    """APT authenticated the indexes; independently match every retained .deb."""
    root = Path("/opt/kb01-provenance")
    verified = []
    for path in sorted(Path("/var/cache/apt/archives").glob("*.deb")):
        values = run("dpkg-deb", "-f", str(path), "Package", "Version", "Architecture")
        fields = dict(line.split(": ", 1) for line in values.splitlines())
        name, version = fields["Package"], fields["Version"]
        stanzas = run("apt-cache", "show", name + "=" + version).split("\n\n")
        records = []
        for stanza in stanzas:
            record = dict(
                line.split(": ", 1)
                for line in stanza.splitlines()
                if ": " in line and not line.startswith(" ")
            )
            if (
                record.get("Version") == version
                and record.get("Architecture") == fields["Architecture"]
            ):
                records.append(record)
        digest = sha(path)
        matches = [r for r in records if r.get("SHA256") == digest]
        if not matches:
            raise ValueError("APT_ARCHIVE_HASH_NOT_IN_AUTHENTICATED_INDEX:" + name)
        verified.append(
            {
                "package": name,
                "version": version,
                "architecture": fields["Architecture"],
                "sha256": digest,
                "repository_filename": matches[0]["Filename"],
                "source": matches[0].get("Source", name),
            }
        )
    signed = []
    for path in sorted(root.glob("*InRelease")):
        checked = subprocess.run(
            [
                "gpgv",
                "--status-fd=1",
                "--keyring",
                "/usr/share/keyrings/debian-archive-keyring.pgp",
                str(path),
            ],
            text=True,
            capture_output=True,
            check=True,
        )
        if "[GNUPG:] VALIDSIG " not in checked.stdout:
            raise ValueError("APT_RELEASE_SIGNATURE_REQUIRED")
        signed.append(
            {
                "file": path.name,
                "sha256": sha(path),
                "signature_status": checked.stdout.splitlines(),
            }
        )
    if len(signed) != 3 or not verified:
        raise ValueError("APT_PROVENANCE_INCOMPLETE")
    indexes = {p.name: sha(p) for p in Path("/var/lib/apt/lists").iterdir() if p.is_file()}
    (root / "apt.json").write_text(
        json.dumps(
            {
                "snapshot": "20261021T000000Z",
                "signature_verification": True,
                "expired_historical_release_valid_until_only": (
                    "disabled for fixed historical snapshot; signatures remain mandatory"
                ),
                "sources": Path("/etc/apt/sources.list").read_text(),
                "signed_release_metadata": signed,
                "authenticated_index_hashes": indexes,
                "verified_downloaded_packages": verified,
                "installed_packages": package_inventory(),
            },
            indent=2,
        )
        + "\n"
    )


def inventory():
    return {
        "apt": json.loads(Path("/opt/kb01-provenance/apt.json").read_text()),
        "installed_packages": package_inventory(),
        "critical_binaries": {
            name: {"sha256": sha(name), "bytes": Path(name).stat().st_size} for name in BINARIES
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apt-build", action="store_true")
    args = parser.parse_args()
    if args.apt_build:
        apt_build()
    else:
        print(json.dumps(inventory()))

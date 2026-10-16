"""Generate one real >1GiB archive at a time; no sparse/padding fake originals."""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT)]


def generate(folder, kind):
    from kb01_archive_fixtures import write_rar4, write_rar5
    from kb01_large_fixtures import write_large_multipage_pdf

    folder.mkdir(parents=True, exist_ok=True)
    originals = []
    for suffix in ("a", "b"):
        source = folder / f"original-multipage-{suffix}.pdf"
        marker = "SYNTHETIC_GOVERNED_TEST_DATA capacity " + suffix.upper()
        if not source.exists():
            write_large_multipage_pdf(source, marker)
        if not source.is_file() or source.is_symlink() or source.stat().st_size <= 500 * 1024**2:
            raise ValueError("GENUINE_LARGE_ORIGINAL_REQUIRED")
        with source.open("rb") as stream:
            if marker.encode() not in stream.read(2048):
                raise ValueError("CAPACITY_FIXTURE_MARKER_MISMATCH")
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        originals.append(
            {
                "name": source.name,
                "bytes": source.stat().st_size,
                "sha256": digest,
                "marker": marker,
            }
        )
    members = [(row["name"], folder / row["name"]) for row in originals]
    if kind == "SINGLE":
        path = members[0][1]
        originals = originals[:1]
    else:
        path = folder / (
            "canonical-capacity-" + kind.lower() + (".zip" if kind == "ZIP" else ".rar")
        )
        if not path.exists():
            if kind == "ZIP":
                with zipfile.ZipFile(
                    path, "x", compression=zipfile.ZIP_STORED, allowZip64=True
                ) as archive:
                    for name, source in members:
                        archive.write(source, name)
            else:
                (write_rar4 if kind == "RAR4" else write_rar5)(path, members)
        if path.stat().st_size <= 1024**3:
            raise ValueError("GENUINE_GIB_ARCHIVE_REQUIRED")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "kind": kind,
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": digest,
        "originals": originals,
        "source_class": "SYNTHETIC_GOVERNED_TEST_DATA",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=("SINGLE", "RAR4", "RAR5", "ZIP"), required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.output, args.kind)))

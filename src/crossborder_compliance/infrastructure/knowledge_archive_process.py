"""Offline libarchive reader. Invoked in a bounded container, never in the HTTP process."""

import argparse
import ctypes
import hashlib
import json
import locale
import stat
import sys
import zipfile
from pathlib import Path

from crossborder_compliance.domain.knowledge_paths import safe_relative_path


def reader():
    lib = ctypes.CDLL("libarchive.so.13")
    signatures = {
        "archive_read_new": (ctypes.c_void_p, []),
        "archive_read_support_filter_all": (ctypes.c_int, [ctypes.c_void_p]),
        "archive_read_support_format_zip": (ctypes.c_int, [ctypes.c_void_p]),
        "archive_read_support_format_rar": (ctypes.c_int, [ctypes.c_void_p]),
        "archive_read_support_format_rar5": (ctypes.c_int, [ctypes.c_void_p]),
        "archive_read_open_filename": (
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t],
        ),
        "archive_read_next_header": (
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
        ),
        "archive_read_data": (
            ctypes.c_ssize_t,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t],
        ),
        "archive_read_free": (ctypes.c_int, [ctypes.c_void_p]),
        "archive_entry_pathname_utf8": (ctypes.c_char_p, [ctypes.c_void_p]),
        "archive_entry_pathname": (ctypes.c_char_p, [ctypes.c_void_p]),
        "archive_entry_size": (ctypes.c_int64, [ctypes.c_void_p]),
        "archive_entry_filetype": (ctypes.c_uint, [ctypes.c_void_p]),
        "archive_entry_symlink": (ctypes.c_char_p, [ctypes.c_void_p]),
        "archive_entry_hardlink": (ctypes.c_char_p, [ctypes.c_void_p]),
        "archive_entry_is_encrypted": (ctypes.c_int, [ctypes.c_void_p]),
    }
    for name, (result, args) in signatures.items():
        function = getattr(lib, name)
        function.restype, function.argtypes = result, args
    return lib


def extract(source, destination, max_bytes, max_entries, max_file_bytes):
    # libarchive's pathname conversion uses libc locale, not Python's UTF-8 mode.
    locale.setlocale(locale.LC_CTYPE, "C.UTF-8")
    with source.open("rb") as raw_source:
        signature = raw_source.read(8)
        if signature.startswith(b"PK"):
            # The version-pinned stdlib reader preserves raw ZIP member names;
            # libarchive can normalize Windows separators before exposing them.
            end = zipfile._EndRecData(raw_source)
            if (
                end is None
                or end[zipfile._ECD_ENTRIES_TOTAL] > max_entries
                or end[zipfile._ECD_SIZE] > max_entries * 2048
            ):
                raise ValueError("ARCHIVE_METADATA_LIMIT")
            with zipfile.ZipFile(source) as archive:
                for member in archive.infolist():
                    safe_relative_path(member.filename.rstrip("/"))
    lib = reader()
    handle = lib.archive_read_new()
    destination = destination.resolve()
    manifest = destination / ".kb01-extracted-manifest.jsonl"
    identities, count, total, files = set(), 0, 0, 0
    buffer = ctypes.create_string_buffer(1024**2)
    digest = hashlib.sha256()
    try:
        for name in (
            "archive_read_support_filter_all",
            "archive_read_support_format_zip",
            "archive_read_support_format_rar",
            "archive_read_support_format_rar5",
        ):
            if getattr(lib, name)(handle) < 0:
                raise ValueError("ARCHIVE_DECODER_NOT_CONFIGURED")
        if lib.archive_read_open_filename(handle, str(source).encode(), 65536) != 0:
            raise ValueError("ARCHIVE_CORRUPT_OR_UNSUPPORTED")
        entry = ctypes.c_void_p()
        with manifest.open("xb") as report:
            while True:
                status = lib.archive_read_next_header(handle, ctypes.byref(entry))
                if status == 1:
                    break
                if status != 0:
                    raise ValueError("ARCHIVE_CORRUPT_OR_UNSUPPORTED")
                count += 1
                if count > max_entries:
                    raise ValueError("ARCHIVE_ENTRY_LIMIT")
                raw = lib.archive_entry_pathname_utf8(entry) or lib.archive_entry_pathname(entry)
                if not raw:
                    raise ValueError("ARCHIVE_FILENAME_MISSING")
                filename = raw.decode("utf-8", errors="strict")
                while filename.startswith("./"):
                    filename = filename[2:]
                filename = safe_relative_path(filename.rstrip("/"))
                key = filename.casefold()
                if key in identities or filename == manifest.name:
                    raise ValueError("ARCHIVE_PATH_COLLISION")
                identities.add(key)
                kind = lib.archive_entry_filetype(entry)
                if (
                    lib.archive_entry_symlink(entry)
                    or lib.archive_entry_hardlink(entry)
                    or kind not in {stat.S_IFREG, stat.S_IFDIR}
                ):
                    raise ValueError("ARCHIVE_LINK_OR_SPECIAL_FILE_REFUSED")
                if lib.archive_entry_is_encrypted(entry):
                    raise ValueError("ENCRYPTED_ARCHIVE_REFUSED")
                target = destination / filename
                if not target.resolve().is_relative_to(destination):
                    raise ValueError("ARCHIVE_PATH_ESCAPE")
                if kind == stat.S_IFDIR:
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if target.suffix.lower() in {".rar", ".zip", ".7z", ".tar", ".gz"}:
                    raise ValueError("NESTED_ARCHIVE_REFUSED")
                declared = lib.archive_entry_size(entry)
                if declared < 0 or declared > max_file_bytes or total + declared > max_bytes:
                    raise ValueError("ARCHIVE_EXPANSION_LIMIT")
                target.parent.mkdir(parents=True, exist_ok=True)
                content_hash, actual = hashlib.sha256(), 0
                with target.open("xb") as output:
                    while True:
                        size = lib.archive_read_data(handle, buffer, len(buffer))
                        if size < 0:
                            raise ValueError("ARCHIVE_INTEGRITY_FAILED")
                        if size == 0:
                            break
                        actual += size
                        total += size
                        if actual > declared or actual > max_file_bytes or total > max_bytes:
                            raise ValueError("ARCHIVE_EXPANSION_LIMIT")
                        chunk = buffer.raw[:size]
                        output.write(chunk)
                        content_hash.update(chunk)
                if actual != declared:
                    raise ValueError("ARCHIVE_SIZE_MISMATCH")
                files += 1
                row = (
                    json.dumps(
                        {
                            "relative_path": filename,
                            "byte_size": actual,
                            "content_sha256": content_hash.hexdigest(),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ).encode()
                    + b"\n"
                )
                report.write(row)
                digest.update(row)
        if not files:
            raise ValueError("ARCHIVE_HAS_NO_FILES")
        return {
            "files": files,
            "entries": count,
            "expanded_bytes": total,
            "manifest_sha256": digest.hexdigest(),
        }
    finally:
        lib.archive_read_free(handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--max-bytes", type=int, required=True)
    parser.add_argument("--max-entries", type=int, required=True)
    parser.add_argument("--max-file-bytes", type=int, required=True)
    args = parser.parse_args()
    if min(args.max_bytes, args.max_entries, args.max_file_bytes) <= 0:
        raise ValueError("INVALID_ARCHIVE_LIMITS")
    try:
        result = extract(
            Path(args.source),
            Path(args.destination),
            args.max_bytes,
            args.max_entries,
            args.max_file_bytes,
        )
        print(json.dumps(result, sort_keys=True))
    except (ValueError, UnicodeError):
        # No untrusted path, original text or decoder diagnostic enters safe evidence.
        print(json.dumps({"error_code": "ARCHIVE_EXTRACTION_REFUSED"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

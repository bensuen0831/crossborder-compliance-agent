"""Bounded catalogue proposals; parsing never creates or publishes knowledge."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol

FIELDS = (
    "sequence",
    "title",
    "language",
    "category",
    "jurisdiction",
    "topic",
    "issuer",
    "format",
    "relative_path",
)
DIMENSIONS = ("language", "category", "jurisdiction", "topic", "issuer")
FORMATS = frozenset({"PDF", "HTML", "TXT", "XHTML", "DOCX", "DOC"})


class ManifestError(ValueError):
    """Stable whole-file validation error; does not expose document contents."""


@dataclass(frozen=True)
class ManifestPolicy:
    columns: Mapping[str, str]
    metadata: Mapping[str, Mapping[str, tuple[str, ...]]]
    max_bytes: int = 32 * 1024 * 1024
    max_expanded_bytes: int = 128 * 1024 * 1024
    max_entries: int = 10000
    max_rows: int = 20000
    max_columns: int = 256
    case_sensitive_paths: bool = True
    csv_encoding: str = "utf-8-sig"
    sheet_name: str | None = None

    def __post_init__(self):
        if (
            set(self.columns) != set(FIELDS)
            or any(not isinstance(v, str) or not v.strip() for v in self.columns.values())
            or len(set(self.columns.values())) != len(FIELDS)
        ):
            raise ManifestError("INVALID_COLUMN_MAPPING")
        if (
            min(
                self.max_bytes,
                self.max_expanded_bytes,
                self.max_entries,
                self.max_rows,
                self.max_columns,
            )
            <= 0
        ):
            raise ManifestError("INVALID_MANIFEST_LIMITS")


@dataclass(frozen=True)
class ManifestIssue:
    row: int
    field: str
    code: str


@dataclass(frozen=True)
class ManifestRecord:
    row: int
    values: tuple[tuple[str, str], ...]
    metadata_refs: tuple[tuple[str, tuple[str, ...]], ...]
    canonical_path: str | None
    status: str
    issues: tuple[ManifestIssue, ...]


@dataclass(frozen=True)
class ManifestPreview:
    content_sha256: str
    records: tuple[ManifestRecord, ...]
    unlisted_files: tuple[str, ...]


def normalize_relative_path(value: str, *, case_sensitive: bool = True) -> str:
    path = unicodedata.normalize("NFC", value.strip()).replace("\\", "/")
    if (
        not path
        or path.startswith("/")
        or re.match(r"^[A-Za-z]:", path)
        or any(ord(c) < 32 or ord(c) == 127 for c in path)
        or ":" in path
        or any(p in {"", ".", ".."} for p in path.split("/"))
    ):
        raise ManifestError("INVALID_RELATIVE_PATH")
    return path if case_sensitive else path.casefold()


class ManifestRowsPort(Protocol):
    def rows(
        self, content: bytes, kind: str, policy: ManifestPolicy
    ) -> Iterable[tuple[list, set[int]]]: ...


def preview_manifest(
    content: bytes,
    *,
    kind: str,
    policy: ManifestPolicy,
    parser: ManifestRowsPort,
    source_paths: tuple[str, ...] | None = None,
) -> ManifestPreview:
    """Metadata mappings must come from the authorized Registry owner, not this parser."""
    rows = iter(parser.rows(content, kind.upper(), policy))
    header, formulas = next(rows, ([], set()))
    if len(header) > policy.max_columns:
        raise ManifestError("MANIFEST_COLUMN_LIMIT")
    names = [str(v).strip() if v is not None else "" for v in header]
    if formulas or any(names.count(v) != 1 for v in policy.columns.values()):
        raise ManifestError("MISSING_OR_AMBIGUOUS_COLUMNS")
    positions = {field: names.index(label) for field, label in policy.columns.items()}
    proposals = []
    inventory = Counter(
        normalize_relative_path(p, case_sensitive=policy.case_sensitive_paths)
        for p in (source_paths or ())
    )
    for number, (cells, formula_indices) in enumerate(rows, 2):
        if number > policy.max_rows + 1:
            raise ManifestError("MANIFEST_ROW_LIMIT")
        if len(cells) > policy.max_columns:
            raise ManifestError("MANIFEST_COLUMN_LIMIT")
        if not any(v is not None and str(v).strip() for v in cells):
            continue
        if len(proposals) >= policy.max_rows:
            raise ManifestError("MANIFEST_ROW_LIMIT")
        values = {
            f: str(cells[i]).strip() if i < len(cells) and cells[i] is not None else ""
            for f, i in positions.items()
        }
        issues = [
            ManifestIssue(number, f, "FORMULA_NOT_ALLOWED")
            for f, i in positions.items()
            if i in formula_indices
        ]
        issues += [
            ManifestIssue(number, f, "REQUIRED_FIELD_MISSING") for f, v in values.items() if not v
        ]
        if not re.fullmatch(r"[1-9][0-9]*", values["sequence"]):
            issues.append(ManifestIssue(number, "sequence", "INVALID_SEQUENCE"))
        refs = []
        for dimension in DIMENSIONS:
            matched = policy.metadata.get(dimension, {}).get(values[dimension])
            if not matched:
                issues.append(ManifestIssue(number, dimension, "METADATA_MAPPING_REQUIRED"))
            else:
                refs.append((dimension, tuple(matched)))
        path = None
        try:
            path = normalize_relative_path(
                values["relative_path"], case_sensitive=policy.case_sensitive_paths
            )
        except ManifestError:
            issues.append(ManifestIssue(number, "relative_path", "INVALID_RELATIVE_PATH"))
        fmt = values["format"].upper()
        if fmt not in FORMATS:
            issues.append(ManifestIssue(number, "format", "UNSUPPORTED_FORMAT"))
        elif path and PurePosixPath(path).suffix[1:].upper() != fmt:
            issues.append(ManifestIssue(number, "format", "FORMAT_PATH_MISMATCH"))
        proposals.append((number, values, refs, path, issues))
    duplicates = Counter(p[3] for p in proposals if p[3])
    records = []
    for number, values, refs, path, issues in proposals:
        if path and duplicates[path] > 1:
            issues.append(ManifestIssue(number, "relative_path", "DUPLICATE_CANDIDATE"))
        if path and inventory[path] > 1:
            issues.append(ManifestIssue(number, "relative_path", "AMBIGUOUS_MATCH"))
        status = (
            "MAPPING_REQUIRED"
            if issues
            else "MANIFEST_IMPORTED"
            if source_paths is None
            else "FILE_MATCHED"
            if inventory[path] == 1
            else "FILE_MISSING"
        )
        records.append(
            ManifestRecord(number, tuple(values.items()), tuple(refs), path, status, tuple(issues))
        )
    unlisted = tuple(sorted(set(inventory) - set(duplicates)))
    return ManifestPreview(hashlib.sha256(content).hexdigest(), tuple(records), unlisted)

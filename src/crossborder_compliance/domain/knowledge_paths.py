"""Neutral filesystem identity validation shared with isolated archive processing."""

import unicodedata
from pathlib import PurePosixPath


def safe_relative_path(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    parts = normalized.split("/")
    if (
        not normalized
        or len(normalized) > 1024
        or "\\" in normalized
        or ":" in normalized
        or any(unicodedata.category(c).startswith("C") for c in normalized)
        or any(p in {"", ".", ".."} or p.endswith((" ", ".")) for p in parts)
        or PurePosixPath(normalized).is_absolute()
    ):
        raise ValueError("UNSAFE_KNOWLEDGE_RELATIVE_PATH")
    return normalized

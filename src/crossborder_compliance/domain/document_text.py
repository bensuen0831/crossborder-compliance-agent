"""Identity-free native text normalization shared by document channels."""

import re


def normalize_document_text(text: object) -> str:
    # Preserve the existing native-parser semantics, including Unicode/RTL text.
    return re.sub(r"\s+", " ", str(text or "")).strip()

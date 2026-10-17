"""Exact original-to-native-source adaptation for the canonical Knowledge ingestion service."""

import re
import tempfile
import unicodedata
from pathlib import Path

from crossborder_compliance.domain.document_text import normalize_document_text
from crossborder_compliance.domain.knowledge_native_parsing import KnowledgeNativeParsingPolicy
from crossborder_compliance.infrastructure.native_language import native_language_hints


def knowledge_source_block(block, policy):
    """Recognize source structure, never applicability, obligations or legal outcomes."""
    text = block["original_text"]
    kind, number, level = "PARAGRAPH", None, 20
    if block.get("table"):
        kind = "TABLE"
    for cue in policy.structure_cues:
        matched = False
        for prefix in cue.prefixes:
            stripped = text.lstrip()
            if not stripped.casefold().startswith(prefix.casefold()):
                continue
            rest = stripped[len(prefix) :].lstrip()
            if cue.numbered:
                match = re.match(
                    r"([\d一二三四五六七八九十百千]+(?:[.-]\d+)*|[IVXLCDM]+)(?=\W|$|[條条章节節部])",
                    rest,
                    re.IGNORECASE,
                )
                if match is None:
                    continue
                suffix = rest[match.end() :].lstrip()
                if cue.number_suffixes and not any(
                    suffix.startswith(value) for value in cue.number_suffixes
                ):
                    continue
                number = match.group(1)
            kind, level, matched = cue.node_type, cue.hierarchy_level, True
            break
        if matched:
            break
    if kind == "PARAGRAPH" and block.get("heading"):
        kind, level = "SECTION", 3
    return {
        "node_type": kind,
        "hierarchy_level": level,
        "canonical_locator": block["locator"],
        "official_number": number,
        "heading": text if block.get("heading") else "",
        "original_text": text,
        "normalized_text": normalize_document_text(unicodedata.normalize("NFC", text)),
        "language_hints": native_language_hints(text),
        "source_locator": block["source_locator"],
    }


class NativeKnowledgeBinarySourceExtractor:
    def __init__(self, storage, parser, working_root: Path):
        self.storage, self.parser, self.working_root = storage, parser, working_root.resolve()

    def extract(self, pinned_source):
        policy = KnowledgeNativeParsingPolicy.model_validate(pinned_source["parser_policy"])
        with tempfile.TemporaryDirectory(
            prefix="knowledge-source-", dir=self.working_root
        ) as folder:
            folder = Path(folder)
            folder.chmod(0o755)
            original = folder / "original"
            measured = self.storage.download(
                pinned_source["object_key"],
                pinned_source["object_version"],
                original,
                pinned_source["declared_bytes"],
            )
            if (
                measured["byte_size"] != pinned_source["declared_bytes"]
                or measured["content_sha256"] != pinned_source["content_sha256"]
            ):
                raise ValueError("KNOWLEDGE_BINARY_PIN_MISMATCH")
            original.chmod(0o644)
            blocks, audit = self.parser.parse(original, pinned_source["declared_format"], policy)
            if audit["needs_ocr"]:
                raise ValueError("KNOWLEDGE_OCR_REQUIRED")
            if not blocks:
                raise ValueError("KNOWLEDGE_NATIVE_TEXT_EMPTY")
            provenance = {
                **audit,
                "policy_definition_id": pinned_source["policy_definition_id"],
                "policy_version_id": pinned_source["policy_version_id"],
                "policy_payload_digest": pinned_source["policy_payload_digest"],
            }
            inputs = []
            parents = []
            for block in blocks:
                node = knowledge_source_block(block, policy)
                level = node.pop("hierarchy_level")
                while parents and parents[-1][0] >= level:
                    parents.pop()
                if parents:
                    node["parent_locator"] = parents[-1][1]
                if level < 20:
                    parents.append((level, node["canonical_locator"]))
                inputs.append(node)
            return inputs, {"native_parser": provenance}

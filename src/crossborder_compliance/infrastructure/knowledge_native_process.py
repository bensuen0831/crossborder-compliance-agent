"""Standalone offline native-extraction process, without any domain-object identity."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from crossborder_compliance.domain.document_text import normalize_document_text
from crossborder_compliance.infrastructure.native_document_extraction import extract_native_blocks


def extract(source, format, destination, policy):
    count, total, digest = 0, 0, hashlib.sha256()
    manifest = destination / ".native-blocks.jsonl"
    with manifest.open("xb") as output:

        def emit(block):
            nonlocal count, total
            if len(block["original_text"]) > policy["max_block_chars"]:
                raise ValueError("NATIVE_TEXT_BLOCK_LIMIT")
            if not normalize_document_text(block["original_text"]):
                return
            count += 1
            row = json.dumps(block, ensure_ascii=False, sort_keys=True).encode() + b"\n"
            total += len(row)
            if count > policy["max_native_blocks"] or total > policy["max_native_output_bytes"]:
                raise ValueError("NATIVE_OUTPUT_LIMIT")
            output.write(row)
            digest.update(row)

        native_audit = extract_native_blocks(source, format, destination, policy, emit)
    return {
        "blocks": count,
        "output_bytes": total,
        "manifest_sha256": digest.hexdigest(),
        "profile": policy["profile"],
        **native_audit,
        "needs_ocr": False,
        "needs_manual_review": bool(
            native_audit.get("ocr_used")
            and native_audit["ocr_minimum_measured_confidence"] < policy["ocr_minimum_confidence"]
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument(
        "--format", required=True, choices=["DOC", "DOCX", "HTML", "PDF", "TXT", "XHTML"]
    )
    parser.add_argument("--destination", required=True)
    parser.add_argument("--policy", required=True)
    args = parser.parse_args()
    try:
        summary = extract(
            Path(args.source), args.format, Path(args.destination), json.loads(args.policy)
        )
        print(json.dumps(summary, sort_keys=True))
    except Exception:
        # Parser diagnostics may contain document fragments. Only a stable code
        # crosses the process boundary; private scratch is disposed by the host.
        print(json.dumps({"error": "NATIVE_EXTRACTION_REFUSED"}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

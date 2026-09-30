from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", "artifacts/phase1a-runtime"))
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

def write_json(name: str, payload: Any) -> Path:
    path = EVIDENCE_DIR / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path

def write_markdown(name: str, title: str, sections: list[tuple[str, str]]) -> Path:
    path = EVIDENCE_DIR / name
    lines = [f"# {title}", ""]
    for heading, body in sections:
        lines.extend([f"## {heading}", "", body.rstrip(), ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path

def bool_mark(value: bool) -> str:
    return "PASS" if value else "FAIL"

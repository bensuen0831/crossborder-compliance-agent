"""Genuine six-format technical originals, labelled synthetic and never legal Gold."""

import argparse
import json
import os
import sys
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]


def generate(folder):
    from kb01_native_fixtures import native_original

    from crossborder_compliance.infrastructure.knowledge_process_sandbox import (
        KnowledgeProcessSandbox,
    )

    sandbox = KnowledgeProcessSandbox(
        os.environ["KB01_TEST_NATIVE_IMAGE"], Path(os.environ["KB01_TEST_NATIVE_WORK_ROOT"])
    )
    folder.mkdir(parents=True, exist_ok=True)
    originals = []
    for locale in ("zh-CN", "zh-HK", "en-US"):
        for format in ("DOC", "DOCX", "HTML", "PDF", "TXT", "XHTML"):
            name = f"kb01-{locale}-{format.lower()}"
            text = f"Article 1. SYNTHETIC_GOVERNED_TEST_DATA. KB01_BROWSER_{locale}_{format}."
            target = folder / (name + "." + format.lower())
            with tempfile.TemporaryDirectory(prefix="browser-fixture-", dir=sandbox.working_root) as work:
                directory = Path(work)
                directory.chmod(0o755)
                path = native_original(format, text, directory, sandbox)
                shutil.copyfile(path, target)
            originals.append(
                {
                    "locale": locale,
                    "format": format,
                    "path": str(target),
                    "marker": f"KB01_BROWSER_{locale}_{format}",
                }
            )
    (folder / "originals.json").write_text(json.dumps(originals, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Use a new owned output directory; no fixture overwrite")
    generate(args.output)

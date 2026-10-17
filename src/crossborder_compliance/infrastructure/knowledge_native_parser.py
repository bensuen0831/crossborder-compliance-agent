"""Host adapter validates bounded native output; canonical ingestion owns its meaning."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from crossborder_compliance.domain.knowledge_native_parsing import KnowledgeNativeParsingPolicy


class IsolatedNativeDocumentParser:
    parser_name = "isolated-native-document-blocks"
    parser_version = "KB01_NATIVE_V1"

    def __init__(self, sandbox):
        self.sandbox = sandbox

    def parse(self, source: Path, declared_format: str, policy: KnowledgeNativeParsingPolicy):
        with tempfile.TemporaryDirectory(prefix="native-", dir=self.sandbox.working_root) as folder:
            output = Path(folder)
            output.chmod(0o755)
            budget = shutil.disk_usage(output).free - 2 * 1024**3
            if budget <= 0:
                raise ValueError("KNOWLEDGE_PROCESS_DISK_BUDGET_EXHAUSTED")
            result = self.sandbox.run(
                "/usr/bin/python3.13",
                [
                    "/opt/knowledge-src/crossborder_compliance/infrastructure/knowledge_native_process.py",
                    "--source",
                    "/input/original",
                    "--destination",
                    "/output",
                    "--format",
                    declared_format,
                    "--policy",
                    json.dumps(policy.model_dump(mode="json"), sort_keys=True),
                ],
                {"/input/original": source},
                min(14400, policy.conversion_timeout_seconds + 60),
                output_directory=output,
                scratch_bytes=min(budget, 2 * 1024**3),
            )
            if result["exit_code"]:
                raise ValueError("NATIVE_EXTRACTION_REFUSED")
            summary = json.loads(result["stdout"])
            manifest = output / ".native-blocks.jsonl"
            if not manifest.is_file() or manifest.stat().st_size > policy.max_native_output_bytes:
                raise ValueError("NATIVE_OUTPUT_LIMIT")
            digest, blocks, locators = hashlib.sha256(), [], set()
            with manifest.open("rb") as records:
                while line := records.readline(policy.max_block_chars * 6 + 2048):
                    if not line.endswith(b"\n"):
                        raise ValueError("NATIVE_TEXT_BLOCK_LIMIT")
                    digest.update(line)
                    block = json.loads(line)
                    if (
                        len(block["original_text"]) > policy.max_block_chars
                        or block["locator"] in locators
                        or not block["locator"].startswith("/")
                    ):
                        raise ValueError("NATIVE_BLOCK_INTEGRITY_FAILED")
                    locators.add(block["locator"])
                    blocks.append(block)
                    if len(blocks) > policy.max_native_blocks:
                        raise ValueError("NATIVE_OUTPUT_LIMIT")
            if len(blocks) != summary["blocks"] or digest.hexdigest() != summary["manifest_sha256"]:
                raise ValueError("NATIVE_MANIFEST_INTEGRITY_FAILED")
            return blocks, {**summary, "parser_image_id": result["image_id"]}


# Existing KB call sites retain a compatible import; there is one implementation.
IsolatedNativeKnowledgeParser = IsolatedNativeDocumentParser

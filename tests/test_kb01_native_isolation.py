"""Genuine six-format native extraction, OCR and untrusted-input fail-closed checks."""

import json
import os
import tempfile
import zipfile
from pathlib import Path

import pytest
from docx import Document
from kb01_large_fixtures import write_large_multipage_pdf

from crossborder_compliance.domain.knowledge_native_parsing import KnowledgeNativeParsingPolicy
from crossborder_compliance.infrastructure.knowledge_native_parser import (
    IsolatedNativeKnowledgeParser,
)
from crossborder_compliance.infrastructure.knowledge_process_sandbox import KnowledgeProcessSandbox

pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def native():
    image = os.environ.get("KB01_TEST_NATIVE_IMAGE")
    root = os.environ.get("KB01_TEST_NATIVE_WORK_ROOT")
    assert image and root, "Real isolated native parsing tooling is required"
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as directory:
        directory = Path(directory)
        directory.chmod(0o755)
        sandbox = KnowledgeProcessSandbox(image, root)
        yield directory, sandbox, IsolatedNativeKnowledgeParser(sandbox)


@pytest.mark.parametrize("format", ["DOC", "DOCX", "HTML", "PDF", "TXT", "XHTML"])
def test_real_six_format_native_originals(native, format):
    directory, sandbox, parser = native
    source = directory / ("source." + format.lower())
    text = "Article 1. SYNTHETIC_KB01_NATIVE_SOURCE. 法規候選. المادة ١."
    if format in {"DOC", "DOCX"}:
        docx = directory / "source.docx"
        doc = Document()
        doc.add_paragraph(text)
        doc.save(docx)
        docx.chmod(0o644)
        if format == "DOC":
            destination = directory / "generated"
            destination.mkdir()
            script = (
                "import subprocess,sys; sys.exit(subprocess.run(["
                "'/usr/lib/libreoffice/program/oosplash',"
                "'-env:UserInstallation=file:///tmp/fixture-profile','--headless',"
                "'--convert-to','doc:MS Word 97','--outdir','/output','/input/original'],"
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode)"
            )
            result = sandbox.run(
                "/usr/bin/python3",
                ["-c", script],
                {"/input/original": docx},
                120,
                output_directory=destination,
                scratch_bytes=1024**3,
            )
            assert result["exit_code"] == 0
            source = destination / "original.doc"
            with source.open("rb") as binary:
                assert binary.read(8) == bytes.fromhex("d0cf11e0a1b11ae1")
    elif format == "PDF":
        write_large_multipage_pdf(
            source, "SYNTHETIC_KB01_NATIVE_SOURCE", pages=1, width=20, height=20
        )
    elif format in {"HTML", "XHTML"}:
        source.write_text("<html><body><p>" + text + "</p></body></html>", encoding="utf-8")
    else:
        source.write_text(text, encoding="utf-16")
    source.chmod(0o644)
    blocks, audit = parser.parse(source, format, KnowledgeNativeParsingPolicy())
    assert any("SYNTHETIC_KB01_NATIVE_SOURCE" in block["original_text"] for block in blocks)
    if format != "PDF":
        assert any(
            "法規候選" in block["original_text"] and "المادة ١" in block["original_text"]
            for block in blocks
        )
    assert audit["blocks"] == len(blocks) and audit["ocr_used"] is False


def test_html_scripts_are_not_evidence_or_executed(native):
    directory, _, parser = native
    source = directory / "source.html"
    source.write_text(
        "<html><body><script>PROHIBITED_SCRIPT</script><style>PROHIBITED_STYLE</style>"
        "<p>Article 1. Visible source.</p>"
        '<img src="http://169.254.169.254/latest/meta-data/"/></body></html>'
    )
    blocks, _ = parser.parse(source, "HTML", KnowledgeNativeParsingPolicy())
    assert [block["original_text"] for block in blocks] == ["Article 1. Visible source."]


def test_actual_vendor_security_fix_and_interpreter_are_present(native):
    """Check the installed vendor backport, not a report or image tag alone."""
    _, sandbox, _ = native
    program = (
        "import json,platform,subprocess; from pathlib import Path; "
        "os_release=dict(line.split('=',1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line); "
        "version=subprocess.check_output(['dpkg-query','-W','-f=${Version}','libxml2'],text=True); "
        "fixed=subprocess.run(['dpkg','--compare-versions',version,'ge','2.9.14+dfsg-1.3ubuntu3.8']).returncode==0; "
        "print(json.dumps({'vendor':os_release['ID'].strip(chr(34)),"
        "'release':os_release['VERSION_ID'].strip(chr(34)),"
        "'python':platform.python_version(),'fixed':fixed,'version':version}))"
    )
    result = sandbox.run("/usr/bin/python3", ["-c", program], {}, 30)
    assert result["exit_code"] == 0
    actual = json.loads(result["stdout"])
    assert actual["vendor"] == "ubuntu" and actual["release"] == "24.04"
    assert actual["python"].startswith("3.12.") and actual["fixed"] is True


def test_xhtml_external_entity_is_refused(native):
    directory, _, parser = native
    source = directory / "source.xhtml"
    source.write_text(
        '<!DOCTYPE html [<!ENTITY stolen SYSTEM "file:///etc/passwd">]><html><body><p>&stolen;</p></body></html>'
    )
    with pytest.raises(ValueError, match="NATIVE_EXTRACTION_REFUSED"):
        parser.parse(source, "XHTML", KnowledgeNativeParsingPolicy())


def test_docx_duplicate_member_universe_is_refused(native):
    directory, _, parser = native
    source = directory / "ambiguous.docx"
    with zipfile.ZipFile(source, "w") as docx:
        docx.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:p><w:r><w:t>Article 1</w:t></w:r></w:p></w:document>",
        )
        docx.writestr("WORD/DOCUMENT.XML", "Conflicting hidden universe")
    with pytest.raises(ValueError, match="NATIVE_EXTRACTION_REFUSED"):
        parser.parse(source, "DOCX", KnowledgeNativeParsingPolicy())


def test_native_output_policy_is_enforced(native):
    directory, _, parser = native
    source = directory / "source.txt"
    source.write_text("Article 1\nArticle 2\n")
    with pytest.raises(ValueError, match="NATIVE_EXTRACTION_REFUSED"):
        parser.parse(source, "TXT", KnowledgeNativeParsingPolicy(max_native_blocks=1))


def test_actual_image_pdf_ocr_preserves_bbox_confidence_and_governed_profile(native):
    from PIL import Image, ImageDraw, ImageFont

    directory, _, parser = native
    source = directory / "scanned.pdf"
    image = Image.new("RGB", (1800, 500), "white")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 44)
    ImageDraw.Draw(image).text(
        (75, 100), "Article 1. SYNTHETIC OCR SOURCE.", font=font, fill="black"
    )
    image.save(source, "PDF", resolution=150)
    source.chmod(0o644)
    blocks, audit = parser.parse(
        source, "PDF", KnowledgeNativeParsingPolicy(ocr_minimum_confidence=1.0)
    )
    assert audit["ocr_used"] is True and audit["native_text_pages"] == []
    assert audit["ocr_pages"] == [1] and audit["needs_manual_review"] is True
    assert any("SYNTHETIC" in block["original_text"] for block in blocks)
    assert all(
        block["source_locator"]["word_bboxes"] and block["source_locator"]["ocr_confidence"] < 1
        for block in blocks
    )
    assert json.loads(json.dumps(audit))["profile"] == "KB01_NATIVE_V1"


def test_existing_document_parser_port_can_use_same_core_without_fake_source_identity(native):
    from uuid import uuid4

    from crossborder_compliance.infrastructure.document_parsers import (
        StreamingNativeDocumentParserAdapter,
        default_native_parsers,
    )

    directory, _, parser = native
    adapter = StreamingNativeDocumentParserAdapter(
        parser, KnowledgeNativeParsingPolicy(), directory
    )
    choices = default_native_parsers(streaming_native=adapter)
    assert choices[0] is adapter
    identity = uuid4()
    result = adapter.parse(
        document_version_id=identity,
        content="Article 1. 原文. المادة ١.".encode(),
        filename="source.txt",
        mime_type="text/plain",
    )
    assert len(result.nodes) == 2
    assert all(node.document_version_id == identity for node in result.nodes)


@pytest.mark.parametrize("memory_bytes", [0, True, 256 * 1024**2 - 1, 8 * 1024**3 + 1])
def test_process_rejects_unbounded_memory_before_launch(tmp_path, memory_bytes):
    sandbox = KnowledgeProcessSandbox("sha256:" + "a" * 64, tmp_path)
    with pytest.raises(ValueError, match="INVALID_KNOWLEDGE_MEMORY_BUDGET"):
        sandbox.run("/usr/bin/clamscan", [], {}, 1, memory_bytes=memory_bytes)


def test_scanner_policy_preserves_legacy_default_and_bounds():
    from pydantic import ValidationError

    from crossborder_compliance.domain.knowledge_management import KnowledgeManagementPolicy

    assert KnowledgeManagementPolicy.model_validate({}).scanner_memory_bytes == 2 * 1024**3
    assert (
        KnowledgeManagementPolicy(scanner_memory_bytes=4 * 1024**3).scanner_memory_bytes
        == 4 * 1024**3
    )
    for value in (256 * 1024**2 - 1, 8 * 1024**3 + 1):
        with pytest.raises(ValidationError):
            KnowledgeManagementPolicy(scanner_memory_bytes=value)

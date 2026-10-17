"""Native file text blocks without Project, Snapshot, Knowledge or legal-result identity.

Executed offline in the same bounded parser sandbox. The owning adapter alone
maps extracted source blocks to canonical Knowledge structure/citations.
"""

import codecs
import csv
import os
import re
import subprocess
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from crossborder_compliance.domain.document_text import normalize_document_text

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def decoded_lines(path):
    with path.open("rb") as binary:
        prefix = binary.read(4)
    encoding = "utf-16" if prefix.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    with path.open("r", encoding=encoding, errors="strict") as source:
        for number, text in enumerate(source, 1):
            yield number, text.rstrip("\r\n")


def refuse_xml_declarations(source, max_bytes):
    total, tail = 0, b""
    while chunk := source.read(65536):
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("NATIVE_XML_SIZE_LIMIT")
        # XML declarations may be UTF-8/16/32. Removing NUL bytes detects ASCII
        # declaration tokens in each encoding; it does not alter parsed content.
        probe = tail + chunk.replace(b"\0", b"").upper()
        if b"<!DOCTYPE" in probe or b"<!ENTITY" in probe:
            raise ValueError("NATIVE_XML_DECLARATION_REFUSED")
        tail = probe[-32:]


def native_command(command, destination, timeout):
    """Native diagnostics stay on task-owned disk rather than unbounded PIPE buffers."""
    stdout, stderr = destination / ".native.stdout", destination / ".native.stderr"
    with stdout.open("wb") as out, stderr.open("wb") as err:
        result = subprocess.run(
            command,
            stdout=out,
            stderr=err,
            timeout=timeout,
            env={
                **os.environ,
                "XDG_CACHE_HOME": "/tmp/native-cache",
                "XDG_CONFIG_HOME": "/tmp/native-config",
                "GSETTINGS_BACKEND": "memory",
                "SAL_USE_VCLPLUGIN": "svp",
            },
        )
    if stdout.stat().st_size + stderr.stat().st_size > 8 * 1024**2:
        raise ValueError("NATIVE_DIAGNOSTIC_LIMIT")
    return result.returncode


def pdf_ocr_blocks(source, destination, pages, policy, emit):
    if not pages:
        return {"ocr_used": False, "ocr_pages": [], "ocr_minimum_measured_confidence": None}
    if not policy["ocr_enabled"]:
        raise ValueError("NATIVE_PDF_OCR_REQUIRED")
    if len(pages) > policy["max_ocr_pages"]:
        raise ValueError("NATIVE_PDF_OCR_PAGE_LIMIT")
    confidences = []
    for page in pages:
        prefix = destination / f"ocr-page-{page}"
        code = native_command(
            [
                "/usr/bin/pdftoppm",
                "-f",
                str(page),
                "-l",
                str(page),
                "-r",
                "150",
                "-png",
                "-singlefile",
                str(source),
                str(prefix),
            ],
            destination,
            policy["conversion_timeout_seconds"],
        )
        image = prefix.with_suffix(".png")
        if code or not image.is_file():
            raise ValueError("NATIVE_PDF_OCR_RENDER_FAILED")
        code = native_command(
            [
                "/usr/bin/tesseract",
                str(image),
                str(prefix),
                "-l",
                "+".join(policy["ocr_languages"]),
                "tsv",
            ],
            destination,
            policy["conversion_timeout_seconds"],
        )
        tsv = prefix.with_suffix(".tsv")
        if code or not tsv.is_file():
            raise ValueError("NATIVE_PDF_OCR_FAILED")
        lines = {}
        with tsv.open(encoding="utf-8") as records:
            for row in csv.DictReader(records, delimiter="\t"):
                text = row.get("text", "")
                confidence = float(row["conf"])
                if not text.strip() or confidence < 0:
                    continue
                key = (row["block_num"], row["par_num"], row["line_num"])
                current = lines.setdefault(key, {"text": [], "confidence": [], "boxes": []})
                current["text"].append(text)
                current["confidence"].append(confidence / 100)
                current["boxes"].append(
                    tuple(int(row[name]) for name in ["left", "top", "width", "height"])
                )
        if not lines:
            raise ValueError("NATIVE_PDF_OCR_EMPTY")
        for key, line in lines.items():
            confidence = sum(line["confidence"]) / len(line["confidence"])
            confidences.append(confidence)
            emit(
                {
                    "original_text": " ".join(line["text"]),
                    "heading": False,
                    "locator": f"/page/{page}/ocr/block/{key[0]}/paragraph/{key[1]}/line/{key[2]}",
                    "source_locator": {
                        "page_no": page,
                        "ocr": True,
                        "render_dpi": 150,
                        "word_bboxes": line["boxes"],
                        "ocr_confidence": confidence,
                    },
                }
            )
        image.unlink()
        tsv.unlink()
    return {
        "ocr_used": True,
        "ocr_pages": pages,
        "ocr_minimum_measured_confidence": min(confidences),
    }


def docx_blocks(path, max_xml_bytes, max_entries):
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) > max_entries:
            raise ValueError("NATIVE_DOCX_ENTRY_LIMIT")
        members = archive.namelist()
        if len({name.casefold() for name in members}) != len(members):
            raise ValueError("NATIVE_DOCX_MEMBER_AMBIGUITY")
        names = ["word/document.xml"] + sorted(
            name
            for name in archive.namelist()
            if re.fullmatch(r"word/(header|footer)\d+\.xml", name)
        )
        if "word/document.xml" not in archive.namelist():
            raise ValueError("NATIVE_DOCX_DOCUMENT_MISSING")
        for name in names:
            member = archive.getinfo(name)
            if member.file_size > max_xml_bytes:
                raise ValueError("NATIVE_XML_SIZE_LIMIT")
            with archive.open(member) as source:
                refuse_xml_declarations(source, max_xml_bytes)
            with archive.open(member) as source:
                index = 0
                tables = []
                table_index = 0
                for event, element in ET.iterparse(source, events=("start", "end")):
                    if event == "start":
                        if element.tag == WORD + "tbl":
                            tables.append(
                                {"table_index": table_index, "row_index": -1, "cell_index": -1}
                            )
                            table_index += 1
                        elif tables and element.tag == WORD + "tr":
                            tables[-1]["row_index"] += 1
                            tables[-1]["cell_index"] = -1
                        elif tables and element.tag == WORD + "tc":
                            tables[-1]["cell_index"] += 1
                        continue
                    if element.tag == WORD + "tbl":
                        tables.pop()
                        element.clear()
                        continue
                    if element.tag != WORD + "p":
                        continue
                    index += 1
                    text = "".join(
                        child.text or ""
                        if child.tag == WORD + "t"
                        else "\t"
                        if child.tag == WORD + "tab"
                        else "\n"
                        if child.tag in {WORD + "br", WORD + "cr"}
                        else ""
                        for child in element.iter()
                    )
                    style = element.find(WORD + "pPr/" + WORD + "pStyle")
                    heading = bool(
                        style is not None
                        and style.get(WORD + "val", "").lower().startswith("heading")
                    )
                    if normalize_document_text(text):
                        yield {
                            "original_text": text,
                            "heading": heading,
                            "table": bool(tables),
                            "locator": f"/{name}/paragraph/{index}",
                            "source_locator": {
                                "xml_member": name,
                                "paragraph_index": index - 1,
                                **(tables[-1] if tables else {}),
                            },
                        }
                    element.clear()


class NativeHTMLBlocks(HTMLParser):
    """Text-only HTML parsing. No script execution, URL fetching or browser state."""

    def __init__(self, emit, max_block_chars):
        super().__init__(convert_charrefs=True)
        self.emit, self.max_block_chars = emit, max_block_chars
        self.hidden = 0
        self.fragments = []
        self.length, self.index = 0, 0
        self.heading = False

    def flush(self):
        text = "".join(self.fragments)
        self.fragments, self.length = [], 0
        if normalize_document_text(text):
            self.index += 1
            self.emit(
                {
                    "original_text": text,
                    "heading": self.heading,
                    "locator": f"/html/block/{self.index}",
                    "source_locator": {"html_block_index": self.index},
                }
            )
        self.heading = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template", "noscript"}:
            self.hidden += 1
        if self.hidden:
            return
        if tag in {
            "p",
            "div",
            "article",
            "section",
            "li",
            "td",
            "th",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }:
            self.flush()
            self.heading = tag.startswith("h") and len(tag) == 2
        if tag == "br":
            self.handle_data("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template", "noscript"} and self.hidden:
            self.hidden -= 1
            return
        if not self.hidden and tag in {
            "p",
            "div",
            "article",
            "section",
            "li",
            "td",
            "th",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }:
            self.flush()

    def handle_data(self, data):
        if not self.hidden:
            self.length += len(data)
            if self.length > self.max_block_chars:
                raise ValueError("NATIVE_TEXT_BLOCK_LIMIT")
            self.fragments.append(data)


def extract_native_blocks(source, format, destination, policy, emit):
    """Emit raw source blocks; this function never constructs formal domain objects."""
    if format == "DOC":
        profile = Path("/tmp/lo-profile/user")
        profile.mkdir(parents=True, exist_ok=True)
        (profile / "registrymodifications.xcu").write_text(
            '<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry">'
            '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
            '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>'
            "</item></oor:items>",
            encoding="utf-8",
        )
        code = native_command(
            [
                "/usr/lib/libreoffice/program/oosplash",
                "-env:UserInstallation=file:///tmp/lo-profile",
                "--headless",
                "--nologo",
                "--nodefault",
                "--norestore",
                "--convert-to",
                "docx",
                "--outdir",
                str(destination),
                str(source),
            ],
            destination,
            policy["conversion_timeout_seconds"],
        )
        source = destination / (source.stem + ".docx")
        if code or not source.is_file():
            raise ValueError("NATIVE_DOC_CONVERSION_FAILED")
        format = "DOCX"
    if format == "DOCX":
        for block in docx_blocks(source, policy["max_xml_bytes"], policy["max_archive_entries"]):
            emit(block)
    elif format == "PDF":
        code = native_command(
            ["/usr/bin/pdfinfo", str(source)], destination, policy["conversion_timeout_seconds"]
        )
        if code:
            raise ValueError("NATIVE_PDF_METADATA_FAILED")
        metadata = (destination / ".native.stdout").read_text(errors="strict")
        match = re.search(r"^Pages:\s+(\d+)$", metadata, re.MULTILINE)
        if match is None:
            raise ValueError("NATIVE_PDF_PAGE_COUNT_MISSING")
        total_pages = int(match.group(1))
        text_file = destination / "native-pdf.txt"
        code = native_command(
            ["/usr/bin/pdftotext", "-layout", "-enc", "UTF-8", str(source), str(text_file)],
            destination,
            policy["conversion_timeout_seconds"],
        )
        if code or not text_file.is_file():
            raise ValueError("NATIVE_PDF_EXTRACTION_FAILED")
        page, page_line = 1, 0
        native_pages = set()
        for _, line in decoded_lines(text_file):
            for index, segment in enumerate(line.split("\f")):
                if index:
                    page += 1
                    page_line = 0
                page_line += 1
                if normalize_document_text(segment):
                    native_pages.add(page)
                    emit(
                        {
                            "original_text": segment,
                            "heading": False,
                            "locator": f"/page/{page}/line/{page_line}",
                            "source_locator": {"page_no": page, "line_no": page_line},
                        }
                    )
        return {
            "pdf_pages": total_pages,
            "native_text_pages": sorted(native_pages),
            **pdf_ocr_blocks(
                source,
                destination,
                [page for page in range(1, total_pages + 1) if page not in native_pages],
                policy,
                emit,
            ),
        }
    elif format == "TXT":
        for line, text in decoded_lines(source):
            if normalize_document_text(text):
                emit(
                    {
                        "original_text": text,
                        "heading": False,
                        "locator": f"/line/{line}",
                        "source_locator": {"line_no": line},
                    }
                )
    elif format in {"HTML", "XHTML"}:
        if format == "XHTML":
            with source.open("rb") as text:
                refuse_xml_declarations(text, policy["max_xml_bytes"])
            # Validate genuine XML before consuming its text through the HTML
            # block reader; malformed/DTD input is not silently repaired.
            for _, element in ET.iterparse(source, events=("end",)):
                element.clear()
        parser = NativeHTMLBlocks(emit, policy["max_block_chars"])
        with source.open("rb") as raw:
            prefix = raw.read(4)
            raw.seek(0)
            decoder = codecs.getincrementaldecoder(
                "utf-16" if prefix.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
            )(errors="strict")
            while chunk := raw.read(65536):
                parser.feed(decoder.decode(chunk, final=False))
            parser.feed(decoder.decode(b"", final=True))
            parser.close()
            parser.flush()
    else:
        raise ValueError("UNSUPPORTED_NATIVE_FORMAT")
    return {"ocr_used": False}

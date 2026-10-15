"""Small genuine synthetic original files; no expected legal result or product authority."""

from pathlib import Path

from docx import Document
from kb01_large_fixtures import write_large_multipage_pdf


def native_original(format, text, directory: Path, sandbox):
    source = directory / ("original." + format.lower())
    if format in {"DOC", "DOCX"}:
        docx = directory / "original.docx"
        document = Document()
        document.add_paragraph(text)
        document.save(docx)
        docx.chmod(0o644)
        if format == "DOC":
            target = directory / "conversion"
            target.mkdir()
            code = (
                "import subprocess,sys; sys.exit(subprocess.run(["
                "'/usr/lib/libreoffice/program/oosplash','-env:UserInstallation=file:///tmp/fixture',"
                "'--headless','--convert-to','doc:MS Word 97',"
                "'--outdir','/output','/input/original'],"
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode)"
            )
            result = sandbox.run(
                "/usr/bin/python3.13",
                ["-c", code],
                {"/input/original": docx},
                120,
                output_directory=target,
                scratch_bytes=1024**3,
            )
            assert result["exit_code"] == 0
            source = target / "original.doc"
    elif format == "PDF":
        write_large_multipage_pdf(source, text, pages=1, width=20, height=20)
    elif format in {"HTML", "XHTML"}:
        source.write_text("<html><body><p>" + text + "</p></body></html>", encoding="utf-8")
    else:
        source.write_text(text, encoding="utf-8")
    source.chmod(0o644)
    return source

"""Real libarchive container, including malicious namespace and expansion inputs."""

import json
import os
import stat
import tempfile
import zipfile
from pathlib import Path

import pytest

from crossborder_compliance.domain.knowledge_management import KnowledgeManagementPolicy
from crossborder_compliance.infrastructure.knowledge_archive_extractor import (
    IsolatedKnowledgeArchiveExtractor,
)
from crossborder_compliance.infrastructure.knowledge_process_sandbox import KnowledgeProcessSandbox

pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def workspace():
    root = os.environ.get("KB01_TEST_ARCHIVE_WORK_ROOT")
    image = os.environ.get("KB01_TEST_ARCHIVE_IMAGE")
    assert root and image, "Actual isolated KB archive tooling is required"
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as directory:
        yield (
            Path(directory),
            IsolatedKnowledgeArchiveExtractor(KnowledgeProcessSandbox(image, root)),
        )


def test_zip_chinese_and_rtl_paths_preserve_exact_originals(workspace):
    directory, extractor = workspace
    source = directory / "source.zip"
    originals = {
        "法律/one.txt": b"Article 1. Synthetic governed source.\n",
        "قانون/two.txt": "المادة ١ — بيانات تجريبية\n".encode(),
    }
    with zipfile.ZipFile(source, "w") as archive:
        for name, content in originals.items():
            archive.writestr(name, content)
    out = directory / "out"
    summary = extractor.extract(source, out, KnowledgeManagementPolicy())
    assert summary["files"] == 2
    for name, content in originals.items():
        assert (out / name).read_bytes() == content
    records = [json.loads(line) for line in summary["manifest_path"].read_text().splitlines()]
    assert {r["relative_path"] for r in records} == originals.keys()


@pytest.mark.parametrize(
    "name",
    [
        "../outside.txt",
        "/outside.txt",
        "a/../../outside.txt",
        "C:/outside.txt",
        "a\\outside.txt",
        "a//outside.txt",
    ],
)
def test_archive_escaping_or_ambiguous_namespace_is_refused(workspace, name):
    directory, extractor = workspace
    source = directory / "source.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(name, "Synthetic unsafe path fixture")
    with pytest.raises(ValueError, match="EXTRACTION_REFUSED"):
        extractor.extract(source, directory / "out", KnowledgeManagementPolicy())
    assert not (directory.parent / "outside.txt").exists()


def test_archive_symlink_is_refused(workspace):
    directory, extractor = workspace
    source = directory / "source.zip"
    item = zipfile.ZipInfo("link.txt")
    item.create_system = 3
    item.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(item, "../../outside")
    with pytest.raises(ValueError, match="EXTRACTION_REFUSED"):
        extractor.extract(source, directory / "out", KnowledgeManagementPolicy())


def test_casefold_collision_is_refused(workspace):
    directory, extractor = workspace
    source = directory / "source.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("Case.txt", "one")
        archive.writestr("case.txt", "two")
    with pytest.raises(ValueError, match="EXTRACTION_REFUSED"):
        extractor.extract(source, directory / "out", KnowledgeManagementPolicy())


def test_nested_archive_is_refused(workspace):
    directory, extractor = workspace
    source = directory / "source.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("nested.rar", b"Rar!\x1a\x07\x00")
    with pytest.raises(ValueError, match="EXTRACTION_REFUSED"):
        extractor.extract(source, directory / "out", KnowledgeManagementPolicy())


@pytest.mark.parametrize(
    "policy",
    [
        KnowledgeManagementPolicy(max_expanded_bytes=3),
        KnowledgeManagementPolicy(max_archive_entries=1),
    ],
)
def test_expansion_and_count_limits_are_enforced(workspace, policy):
    directory, extractor = workspace
    source = directory / "source.zip"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("one.txt", "x" * 10000)
        archive.writestr("two.txt", "two")
    with pytest.raises(ValueError, match="EXTRACTION_REFUSED"):
        extractor.extract(source, directory / "out", policy)


def test_corrupt_zip_payload_is_refused(workspace):
    directory, extractor = workspace
    source = directory / "source.zip"
    marker = b"Original unique integrity fixture."
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("one.txt", marker)
    data = source.read_bytes()
    offset = data.index(marker)
    source.write_bytes(data[:offset] + b"X" + data[offset + 1 :])
    with pytest.raises(ValueError, match="EXTRACTION_REFUSED"):
        extractor.extract(source, directory / "out", KnowledgeManagementPolicy())


@pytest.mark.parametrize("version", [4, 5])
def test_genuine_rar4_rar5_are_decoded_by_real_isolated_libarchive(workspace, version):
    from kb01_archive_fixtures import write_rar4, write_rar5

    directory, extractor = workspace
    original = directory / "original.txt"
    original.write_bytes(b"Article 1. Genuine synthetic RAR payload.\n")
    archive = directory / "source.rar"
    name = "one.txt" if version == 4 else "法律/one.txt"
    (write_rar4 if version == 4 else write_rar5)(archive, [(name, original)])
    summary = extractor.extract(archive, directory / "out", KnowledgeManagementPolicy())
    assert summary["files"] == 1
    assert (directory / "out" / name).read_bytes() == original.read_bytes()

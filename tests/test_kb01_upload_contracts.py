"""Binary transport rejects unsafe scope and path identities before any provider call."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from crossborder_compliance.domain.knowledge_upload import (
    KnowledgeUploadPartRequest,
    StartKnowledgeUpload,
    safe_relative_path,
)


@pytest.mark.parametrize(
    "path",
    [
        "../a.txt",
        "/a.txt",
        "a/../b.txt",
        "a\\b.txt",
        "C:/a.txt",
        "a//b.txt",
        "a\x00.txt",
        "a\u202eb.txt",
        "a. /b.txt",
        "a/./b.txt",
    ],
)
def test_knowledge_upload_rejects_ambiguous_or_escaping_paths(path):
    with pytest.raises(ValueError, match="UNSAFE_KNOWLEDGE_RELATIVE_PATH"):
        safe_relative_path(path)


def test_knowledge_folder_identity_is_unicode_normalized_and_retained():
    assert safe_relative_path("法規/港澳/a.txt") == "法規/港澳/a.txt"
    assert safe_relative_path("Cafe\u0301/a.txt") == "Café/a.txt"


def upload(**changes):
    return StartKnowledgeUpload(
        **dict(
            relative_path="input.txt",
            declared_format="TXT",
            declared_bytes=600000001,
            content_sha256="a" * 64,
            idempotency_key="transport",
            **changes,
        )
    )


def test_upload_manifest_supports_large_declarations_without_a_fake_capacity_claim():
    assert upload().declared_bytes == 600000001
    value = StartKnowledgeUpload(
        relative_path="archive.rar",
        declared_format="RAR",
        declared_bytes=1200000001,
        content_sha256="b" * 64,
        idempotency_key="archive",
    )
    assert value.knowledge_version_id is None


def test_upload_target_requires_exact_version_cas():
    with pytest.raises(ValidationError, match="TARGET_CAS_REQUIRED"):
        upload(knowledge_version_id=uuid4())
    assert upload(knowledge_version_id=uuid4(), expected_record_version=1)


def test_archive_cannot_be_a_formal_knowledge_document_version():
    with pytest.raises(ValidationError, match="ARCHIVE_IS_NOT"):
        StartKnowledgeUpload(
            relative_path="a.zip",
            declared_format="ZIP",
            declared_bytes=10,
            content_sha256="b" * 64,
            idempotency_key="archive",
            knowledge_version_id=uuid4(),
            expected_record_version=1,
        )


@pytest.mark.parametrize("digest", ["", "f" * 63, "F" * 64, "0" * 65, "z" * 64])
def test_part_checksum_is_bounded_and_unambiguous(digest):
    with pytest.raises(ValidationError, match="INVALID_CONTENT_SHA256"):
        KnowledgeUploadPartRequest(part_number=1, content_sha256=digest)


def test_transport_actor_and_storage_key_are_server_owned():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        upload(actor_id="spoofed")

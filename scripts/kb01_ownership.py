"""Finite KB01 V2 scope successor, authenticated from committed Git blobs.

No historical manifest or legal-engine algorithm is replaced. Tests and source
outside the explicit management adapter paths remain byte-preserved.
"""

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

BASE = "060cbb5a20a9f8f70fa88dbefb8b5feb404c460d"
RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay.json"
SECOND_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v2.json"
SECOND_SEAL = "61676b02689c407cfcc6e6c91b8a6b553de6d616"
THIRD_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v3.json"
THIRD_SEAL = "e012d2a35c68e1c1ad9ccec879d78e5a45ffc208"
THIRD_SOURCE = "76e4f0dd6a5797060b88b917d52b5bceb624bc19"
SUCCESSOR_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v4.json"
FIRST_SEAL = "a95d5f05f46566d7e58417a8c9cb2214c6d028f0"
FIRST_SOURCE = "6f0f448fbe5d72494d2756bca30a3f74437e1f63"
PREVIOUS = "evidence/stage1-full-e2e/r3/approved_owner_overlay.json"
PATHS = frozenset(
    (
        "pyproject.toml",
        "alembic/versions/0023_kb01_evidence_source_reference.py",
        "src/crossborder_compliance/application/document_ports.py",
        "src/crossborder_compliance/application/knowledge_ports.py",
        "src/crossborder_compliance/application/knowledge_services.py",
        "src/crossborder_compliance/domain/document_text.py",
        "src/crossborder_compliance/domain/knowledge_native_parsing.py",
        "src/crossborder_compliance/domain/native_structure.py",
        "src/crossborder_compliance/infrastructure/document_parsers.py",
        "src/crossborder_compliance/infrastructure/knowledge_batch_ingestion_worker.py",
        "src/crossborder_compliance/infrastructure/knowledge_binary_extraction.py",
        "src/crossborder_compliance/infrastructure/knowledge_management_worker.py",
        "src/crossborder_compliance/infrastructure/knowledge_native_parser.py",
        "src/crossborder_compliance/infrastructure/knowledge_native_process.py",
        "src/crossborder_compliance/infrastructure/native_document_extraction.py",
        "src/crossborder_compliance/infrastructure/native_language.py",
        "src/crossborder_compliance/infrastructure/persistence/models.py",
        "src/crossborder_compliance/interfaces/api/knowledge_binary_ingestion_schemas.py",
        "src/crossborder_compliance/interfaces/api/routes/knowledge_binary_ingestion.py",
        "tests/kb01_historical_schema.py",
        "tests/kb01_native_fixtures.py",
        "tests/test_kb01_binary_ingestion_postgres.py",
        "tests/test_kb01_evidence_reference_migrations.py",
        "tests/test_kb01_native_isolation.py",
        "tests/test_kb01_native_structure.py",
        "alembic/versions/0022_kb01_binary_transport.py",
        "src/crossborder_compliance/application/knowledge_binary_ports.py",
        "src/crossborder_compliance/application/knowledge_uploads.py",
        "src/crossborder_compliance/domain/knowledge_batches.py",
        "src/crossborder_compliance/domain/knowledge_paths.py",
        "src/crossborder_compliance/domain/knowledge_upload.py",
        "src/crossborder_compliance/infrastructure/knowledge_archive_extractor.py",
        "src/crossborder_compliance/infrastructure/knowledge_archive_process.py",
        "src/crossborder_compliance/infrastructure/knowledge_binary_storage.py",
        "src/crossborder_compliance/infrastructure/knowledge_import_worker.py",
        "src/crossborder_compliance/infrastructure/knowledge_process_sandbox.py",
        "src/crossborder_compliance/infrastructure/knowledge_upload_worker.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_batches.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_upload_models.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_uploads.py",
        "src/crossborder_compliance/interfaces/api/knowledge_batch_schemas.py",
        "src/crossborder_compliance/interfaces/api/knowledge_upload_schemas.py",
        "src/crossborder_compliance/interfaces/api/routes/knowledge_batches.py",
        "src/crossborder_compliance/interfaces/api/routes/knowledge_uploads.py",
        "tests/kb01_archive_fixtures.py",
        "tests/kb01_large_fixtures.py",
        "tests/test_kb01_archive_isolation.py",
        "tests/test_kb01_batches_postgres.py",
        "tests/test_kb01_binary_migrations.py",
        "tests/test_kb01_upload_contracts.py",
        "tests/test_kb01_upload_postgres.py",
        "scripts/stage1_business_architecture.py",
        "scripts/m2a_ownership.py",
        "ARCHITECTURE_RULES.md",
        "scripts/kb01_architecture_check.py",
        "scripts/architecture_rule_check.py",
        "tests/test_kb01_architecture.py",
        "tests/test_m2d_architecture.py",
        "tests/test_m2e_r1_architecture.py",
        "tests/test_phase1kb_architecture.py",
        "alembic/env.py",
        "alembic/versions/0021_kb01_taxonomy_operations.py",
        "scripts/kb01_ownership.py",
        "scripts/stage1_e2e_r3_ownership.py",
        "src/crossborder_compliance/application/knowledge_document_management.py",
        "src/crossborder_compliance/application/knowledge_manifest.py",
        "src/crossborder_compliance/application/knowledge_taxonomy.py",
        "src/crossborder_compliance/domain/knowledge_management.py",
        "src/crossborder_compliance/infrastructure/knowledge_manifest_parser.py",
        "src/crossborder_compliance/infrastructure/persistence/compliance_profile_governance.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_document_management.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_management_models.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_models.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_taxonomy.py",
        "src/crossborder_compliance/infrastructure/persistence/metadata_models.py",
        "src/crossborder_compliance/infrastructure/persistence/metadata_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/taxonomy_governance.py",
        "src/crossborder_compliance/infrastructure/registry_catalog.py",
        "src/crossborder_compliance/interfaces/api/knowledge_management_schemas.py",
        "src/crossborder_compliance/interfaces/api/main.py",
        "src/crossborder_compliance/interfaces/api/routes/admin_metadata.py",
        "src/crossborder_compliance/interfaces/api/routes/knowledge_document_management.py",
        "src/crossborder_compliance/interfaces/api/routes/knowledge_management.py",
        "src/crossborder_compliance/interfaces/api/routes/metadata.py",
        "tests/test_kb01_document_management_postgres.py",
        "tests/test_kb01_ownership.py",
        "tests/test_kb01_taxonomy_migrations.py",
        "tests/test_kb01_taxonomy_postgres.py",
        "tests/test_knowledge_manifest.py",
        "tests/test_stage1_candidate_governance_migrations.py",
        "tests/test_stage1_decision_compatibility_migrations.py",
    )
)


def overlay(root):
    root = Path(root).resolve()

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "core.quotepath=false", *args], cwd=root, stderr=subprocess.DEVNULL
        )

    def ancestor(a, b):
        return (
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", a, b], cwd=root, stderr=subprocess.DEVNULL
            ).returncode
            == 0
        )

    def blobs(source, paths):
        with tarfile.open(
            fileobj=io.BytesIO(git("archive", source, "--", *sorted(paths)))
        ) as archive:
            return {
                item.name: archive.extractfile(item).read() for item in archive if item.isfile()
            }

    try:
        baseline_paths = git("ls-tree", "-r", "--name-only", BASE).decode().splitlines()
        originals = blobs(BASE, baseline_paths)
        # The existing domain model is shared with every formal owner. KB01 C
        # permits only the byte-preserving Evidence reference schema extension.
        model_path = "src/crossborder_compliance/infrastructure/persistence/models.py"
        expected_model = (
            originals[model_path]
            .decode()
            .replace("    UniqueConstraint,\n", "    UniqueConstraint,\n    text,\n", 1)
        )
        expected_model = expected_model.replace(
            '    __table_args__ = (Index("ix_evidence_source", "tenant_id", "source_ref"),)',
            "    __table_args__ = (\n"
            '        Index("ix_evidence_source", "tenant_id", text("md5(source_ref)")),\n'
            '        CheckConstraint("octet_length(source_ref) <= 32768", '
            'name="ck_evidence_source_reference_bytes"),\n    )',
            1,
        )
        expected_model = expected_model.replace(
            "    source_ref: Mapped[str] = mapped_column(String(500), nullable=False)",
            "    source_ref: Mapped[str] = mapped_column(Text, nullable=False)",
            1,
        )
        if (root / model_path).read_bytes() != expected_model.encode():
            return False, {}, None
        previous = json.loads(originals[PREVIOUS])
        if (root / PREVIOUS).read_bytes() != originals[PREVIOUS] or not ancestor(
            previous["source_sha"], BASE
        ):
            return False, {}, None
        historical = blobs(previous["source_sha"], previous["paths"])
        if any(
            hashlib.sha256(historical[path]).hexdigest() != digest
            for path, digest in previous["paths"].items()
        ):
            return False, {}, None
        first_bytes = git("show", FIRST_SEAL + ":" + RECORD)
        if (root / RECORD).read_bytes() != first_bytes or not ancestor(FIRST_SEAL, "HEAD"):
            return False, {}, None
        first = json.loads(first_bytes)
        if first["source_sha"] != FIRST_SOURCE or first["base_sha"] != BASE:
            return False, {}, None
        first_blobs = blobs(FIRST_SOURCE, first["paths"])
        if any(
            hashlib.sha256(first_blobs[path]).hexdigest() != digest
            for path, digest in first["paths"].items()
        ):
            return False, {}, None
        second_bytes = git("show", SECOND_SEAL + ":" + SECOND_RECORD)
        if (root / SECOND_RECORD).read_bytes() != second_bytes or not ancestor(SECOND_SEAL, "HEAD"):
            return False, {}, None
        second = json.loads(second_bytes)
        if second["base_sha"] != BASE or not ancestor(FIRST_SEAL, second["source_sha"]):
            return False, {}, None
        second_blobs = blobs(second["source_sha"], second["paths"])
        if any(
            hashlib.sha256(second_blobs[path]).hexdigest() != digest
            for path, digest in second["paths"].items()
        ):
            return False, {}, None
        # The first completed KB migration is frozen as well as release 0001–0020.
        migration21 = "alembic/versions/0021_kb01_taxonomy_operations.py"
        if (root / migration21).read_bytes() != first_blobs[migration21]:
            return False, {}, None
        third_bytes = git("show", THIRD_SEAL + ":" + THIRD_RECORD)
        if (root / THIRD_RECORD).read_bytes() != third_bytes or not ancestor(THIRD_SEAL, "HEAD"):
            return False, {}, None
        third = json.loads(third_bytes)
        if third["source_sha"] != THIRD_SOURCE or third["base_sha"] != BASE:
            return False, {}, None
        third_blobs = blobs(THIRD_SOURCE, third["paths"])
        if any(
            hashlib.sha256(third_blobs[path]).hexdigest() != digest
            for path, digest in third["paths"].items()
        ):
            return False, {}, None
        migration22 = "alembic/versions/0022_kb01_binary_transport.py"
        if (root / migration22).read_bytes() != third_blobs[migration22]:
            return False, {}, None
        record = json.loads((root / SUCCESSOR_RECORD).read_text())
        expected = set(previous["paths"]) | PATHS
        source = record["source_sha"]
        if (
            record["base_sha"] != BASE
            or record["scope"] != "STAGE1-GAP-KB01-MASTER_V2.0"
            or set(record["paths"]) != expected
            or not ancestor(BASE, source)
            or not ancestor(THIRD_SEAL, source)
            or not ancestor(source, "HEAD")
        ):
            return False, {}, None
        committed = blobs(source, expected)
        if any(
            hashlib.sha256(committed[path]).hexdigest() != digest
            or (root / path).read_bytes() != committed[path]
            for path, digest in record["paths"].items()
        ):
            return False, {}, None
        if any(
            (root / path).read_bytes() != originals[path]
            for path in baseline_paths
            if path not in PATHS
        ):
            return False, {}, None
        changes = (
            set(git("diff", "--name-only", BASE, source).decode().splitlines())
            | set(git("diff", "--name-only", BASE).decode().splitlines())
            | set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
        )
        if any(
            path not in PATHS
            and not path.startswith(("docs/stage1-gap-kb01/", "evidence/stage1-gap-kb01/"))
            for path in changes
        ):
            return False, {}, None
        # No path exception includes historical migrations or legal engines.
        if any(
            path.startswith("alembic/versions/")
            and path.split("/")[-1][:4].isdigit()
            and int(path.split("/")[-1][:4]) <= 20
            for path in PATHS
        ):
            return False, {}, None
        return True, record["paths"], source
    except (OSError, KeyError, ValueError, TypeError, subprocess.CalledProcessError):
        return False, {}, None


def authenticated_paths(root, source):
    """Extend a prior owner's finite bounds only with this exact proven successor."""
    valid, paths, successor_source = overlay(root)
    if not valid or successor_source != source:
        raise ValueError("KB01 successor source does not authenticate")
    return frozenset(paths)

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
FOURTH_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v4.json"
FOURTH_SEAL = "0deff721aa52d848def1eb32f579220017b13f40"
FOURTH_SOURCE = "cfe7f9e4ad47c9695b9097344b1ef2a9abf7ba69"
FIFTH_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v5.json"
FIFTH_SEAL = "e01b8923a00d3c26c34c1d99d789d6e327c1e88a"
FIFTH_SOURCE = "2918e4290a7f66bdf892ab74971d8ad3addcb1d3"
SIXTH_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v6.json"
SIXTH_SEAL = "2a1010570248dee3e9539e26f64a254b2d7fea91"
SIXTH_SOURCE = "f5bc2a6ef5e8fd3210720f0e0753c9fb5b35b310"
SEVENTH_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v7.json"
SEVENTH_SEAL = "2e4acdc3f355ed28a1d3e4792f9cbbb9cbbff098"
SEVENTH_SOURCE = "84806fe67801568116c2b98fb281685a27959213"
EIGHTH_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v8.json"
EIGHTH_SEAL = "876f5a3a7312c45b104978c5ab41def02633f447"
EIGHTH_SOURCE = "36283d2ff89b6d8b2648661333a3b63221ddac1b"
NINTH_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v9.json"
NINTH_SEAL = "9c47f40432f32ce4cae3bd19b2901b9774d6f7ef"
NINTH_SOURCE = "7002d906e29984a4e91d4eeb8d6299c405c13aee"
TENTH_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v10.json"
TENTH_SEAL = "c905538d3b754df68e25ab1d127bc98a989d45fc"
TENTH_SOURCE = "65556e5fc4e99df5f8cd69e5dff676a492995231"
ELEVENTH_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v11.json"
ELEVENTH_SEAL = "18fdbe705dc109fba5002f2bcebbdec81273f664"
ELEVENTH_SOURCE = "2e8e17b344f2c4fd16684af0f6a45336b4820fbe"
SUCCESSOR_RECORD = "evidence/stage1-gap-kb01/approved_owner_overlay_v12.json"
FIRST_SEAL = "a95d5f05f46566d7e58417a8c9cb2214c6d028f0"
FIRST_SOURCE = "6f0f448fbe5d72494d2756bca30a3f74437e1f63"
PREVIOUS = "evidence/stage1-full-e2e/r3/approved_owner_overlay.json"
PATHS = frozenset(
    (
        "frontend/e2e/kb01-safe-evidence.ts",
        "frontend/e2e/kb01-taxonomy.spec.ts",
        "frontend/src/test/kb01-evidence.test.ts",
        "frontend/e2e/kb01-capacity.spec.ts",
        "frontend/e2e/kb01-manifest.spec.ts",
        "scripts/kb01/generate_capacity.py",
        "scripts/kb01/verify_ci.py",
        "tests/test_kb01_ci_evidence.py",
        ".github/actions/kb01-tools/action.yml",
        ".github/workflows/kb01-knowledge-management.yml",
        ".github/workflows/m2e-external-agent-api.yml",
        ".github/workflows/phase1a-runtime-smoke.yml",
        ".github/workflows/phase1kb-multi-provider-llm-governance.yml",
        ".github/workflows/stage1-candidate-governance.yml",
        "alembic/versions/0024_kb01_import_manifest_records.py",
        "frontend/src/features/knowledge-management/KnowledgeScopeControls.test.tsx",
        "frontend/src/features/knowledge-management/KnowledgeScopeControls.tsx",
        "frontend/src/features/knowledge-management/ManifestPanel.test.tsx",
        "frontend/src/features/knowledge-management/ManifestPanel.tsx",
        "scripts/kb01/Containerfile",
        "scripts/kb01/build_tools.py",
        "scripts/kb01/ci_services.py",
        "scripts/kb01/official_signatures.py",
        "scripts/stage1_alpha_integrity.py",
        "src/crossborder_compliance/application/knowledge_manifest_imports.py",
        "src/crossborder_compliance/domain/knowledge_manifest_governance.py",
        "src/crossborder_compliance/domain/knowledge_manifest_policy.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_manifest_imports.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_manifest_models.py",
        "src/crossborder_compliance/interfaces/api/knowledge_manifest_schemas.py",
        "src/crossborder_compliance/interfaces/api/routes/knowledge_manifests.py",
        "tests/test_kb01_manifest_imports_postgres.py",
        "tests/test_kb01_manifest_migrations.py",
        "tests/test_kb01_scope_management_postgres.py",
        "frontend/vite.config.ts",
        "frontend/src/api/client.ts",
        "frontend/src/api/client.test.ts",
        "frontend/e2e/kb01-management.spec.ts",
        "frontend/src/features/knowledge-management/TaxonomyTree.tsx",
        "frontend/src/features/knowledge-management/TaxonomyTree.test.tsx",
        "frontend/src/features/knowledge-management/TranslationAlignment.tsx",
        "frontend/src/features/knowledge-management/TranslationAlignment.test.tsx",
        "scripts/kb01/export_acceptance_templates.py",
        "scripts/kb01/generate_fixtures.py",
        "scripts/kb01/uat.py",
        "src/crossborder_compliance/application/regulatory_acceptance.py",
        "src/crossborder_compliance/domain/knowledge_translation_alignment.py",
        "src/crossborder_compliance/domain/regulatory_acceptance.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_translation_alignment.py",
        "src/crossborder_compliance/infrastructure/persistence/regulatory_acceptance.py",
        "src/crossborder_compliance/infrastructure/persistence/regulatory_acceptance_governance.py",
        "src/crossborder_compliance/interfaces/api/regulatory_acceptance_schemas.py",
        "src/crossborder_compliance/interfaces/api/routes/knowledge_translation_alignment.py",
        "src/crossborder_compliance/interfaces/api/routes/regulatory_acceptance.py",
        "tests/test_kb01_acceptance_readiness.py",
        "tests/test_kb01_acceptance_readiness_postgres.py",
        "tests/test_kb01_translation_alignment_postgres.py",
        "frontend/eslint.config.js",
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/src/features/admin/AdminFeature.tsx",
        "frontend/src/features/admin/admin.css",
        "frontend/src/features/admin/resources.ts",
        "frontend/src/locales/en-US.json",
        "frontend/src/locales/zh-CN.json",
        "frontend/src/locales/zh-HK.json",
        "frontend/src/api/kb01-generated.ts",
        "frontend/src/api/kb01-openapi.json",
        "scripts/kb01_export_contracts.py",
        "src/crossborder_compliance/infrastructure/persistence/knowledge_statistics.py",
        "src/crossborder_compliance/interfaces/api/routes/knowledge_statistics.py",
        "tests/test_kb01_statistics_postgres.py",
        "tests/test_kb01_batch_recovery_postgres.py",
        "frontend/src/features/knowledge-management/KnowledgeManagement.tsx",
        "frontend/src/features/knowledge-management/TaxonomyEditor.tsx",
        "frontend/src/features/knowledge-management/client.ts",
        "frontend/src/features/knowledge-management/hash.worker.ts",
        "frontend/src/features/knowledge-management/management.test.tsx",
        "frontend/src/features/knowledge-management/streamDigest.test.ts",
        "frontend/src/features/knowledge-management/streamDigest.ts",
        "frontend/src/features/knowledge-management/uploads.ts",
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
            '        Index("ix_evidence_source", "tenant_id", text("md5(source_ref)")).ddl_if(\n'
            '            dialect="postgresql"\n'
            "        ),\n"
            "        CheckConstraint(\n"
            '            "octet_length(source_ref) <= 32768", '
            'name="ck_evidence_source_reference_bytes"\n'
            '        ).ddl_if(dialect="postgresql"),\n    )',
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
        fourth_bytes = git("show", FOURTH_SEAL + ":" + FOURTH_RECORD)
        if (root / FOURTH_RECORD).read_bytes() != fourth_bytes or not ancestor(FOURTH_SEAL, "HEAD"):
            return False, {}, None
        fourth = json.loads(fourth_bytes)
        if fourth["source_sha"] != FOURTH_SOURCE or fourth["base_sha"] != BASE:
            return False, {}, None
        fourth_blobs = blobs(FOURTH_SOURCE, fourth["paths"])
        if any(
            hashlib.sha256(fourth_blobs[path]).hexdigest() != digest
            for path, digest in fourth["paths"].items()
        ):
            return False, {}, None
        migration23 = "alembic/versions/0023_kb01_evidence_source_reference.py"
        if (root / migration23).read_bytes() != fourth_blobs[migration23]:
            return False, {}, None
        fifth_bytes = git("show", FIFTH_SEAL + ":" + FIFTH_RECORD)
        if (root / FIFTH_RECORD).read_bytes() != fifth_bytes or not ancestor(FIFTH_SEAL, "HEAD"):
            return False, {}, None
        fifth = json.loads(fifth_bytes)
        if fifth["source_sha"] != FIFTH_SOURCE or fifth["base_sha"] != BASE:
            return False, {}, None
        fifth_blobs = blobs(FIFTH_SOURCE, fifth["paths"])
        if any(
            hashlib.sha256(fifth_blobs[path]).hexdigest() != digest
            for path, digest in fifth["paths"].items()
        ):
            return False, {}, None
        sixth_bytes = git("show", SIXTH_SEAL + ":" + SIXTH_RECORD)
        if (root / SIXTH_RECORD).read_bytes() != sixth_bytes or not ancestor(SIXTH_SEAL, "HEAD"):
            return False, {}, None
        sixth = json.loads(sixth_bytes)
        if sixth["source_sha"] != SIXTH_SOURCE or sixth["base_sha"] != BASE:
            return False, {}, None
        sixth_blobs = blobs(SIXTH_SOURCE, sixth["paths"])
        if any(
            hashlib.sha256(sixth_blobs[path]).hexdigest() != digest
            for path, digest in sixth["paths"].items()
        ):
            return False, {}, None
        seventh_bytes = git("show", SEVENTH_SEAL + ":" + SEVENTH_RECORD)
        if (root / SEVENTH_RECORD).read_bytes() != seventh_bytes or not ancestor(
            SEVENTH_SEAL, "HEAD"
        ):
            return False, {}, None
        seventh = json.loads(seventh_bytes)
        if seventh["source_sha"] != SEVENTH_SOURCE or seventh["base_sha"] != BASE:
            return False, {}, None
        seventh_blobs = blobs(SEVENTH_SOURCE, seventh["paths"])
        if any(
            hashlib.sha256(seventh_blobs[path]).hexdigest() != digest
            for path, digest in seventh["paths"].items()
        ):
            return False, {}, None
        eighth_bytes = git("show", EIGHTH_SEAL + ":" + EIGHTH_RECORD)
        if (root / EIGHTH_RECORD).read_bytes() != eighth_bytes or not ancestor(EIGHTH_SEAL, "HEAD"):
            return False, {}, None
        eighth = json.loads(eighth_bytes)
        if eighth["source_sha"] != EIGHTH_SOURCE or eighth["base_sha"] != BASE:
            return False, {}, None
        eighth_blobs = blobs(EIGHTH_SOURCE, eighth["paths"])
        if any(
            hashlib.sha256(eighth_blobs[path]).hexdigest() != digest
            for path, digest in eighth["paths"].items()
        ):
            return False, {}, None
        migration24 = "alembic/versions/0024_kb01_import_manifest_records.py"
        if (root / migration24).read_bytes() != eighth_blobs[migration24]:
            return False, {}, None
        ninth_bytes = git("show", NINTH_SEAL + ":" + NINTH_RECORD)
        if (root / NINTH_RECORD).read_bytes() != ninth_bytes or not ancestor(NINTH_SEAL, "HEAD"):
            return False, {}, None
        ninth = json.loads(ninth_bytes)
        if ninth["source_sha"] != NINTH_SOURCE or ninth["base_sha"] != BASE:
            return False, {}, None
        ninth_blobs = blobs(NINTH_SOURCE, ninth["paths"])
        if any(
            hashlib.sha256(ninth_blobs[path]).hexdigest() != digest
            for path, digest in ninth["paths"].items()
        ):
            return False, {}, None
        tenth_bytes = git("show", TENTH_SEAL + ":" + TENTH_RECORD)
        if (root / TENTH_RECORD).read_bytes() != tenth_bytes or not ancestor(TENTH_SEAL, "HEAD"):
            return False, {}, None
        tenth = json.loads(tenth_bytes)
        if tenth["source_sha"] != TENTH_SOURCE or tenth["base_sha"] != BASE:
            return False, {}, None
        tenth_blobs = blobs(TENTH_SOURCE, tenth["paths"])
        if any(
            hashlib.sha256(tenth_blobs[path]).hexdigest() != digest
            for path, digest in tenth["paths"].items()
        ):
            return False, {}, None
        eleventh_bytes = git("show", ELEVENTH_SEAL + ":" + ELEVENTH_RECORD)
        if (
            (root / ELEVENTH_RECORD).read_bytes() != eleventh_bytes
            or not ancestor(ELEVENTH_SEAL, "HEAD")
        ):
            return False, {}, None
        eleventh = json.loads(eleventh_bytes)
        if eleventh["source_sha"] != ELEVENTH_SOURCE or eleventh["base_sha"] != BASE:
            return False, {}, None
        eleventh_blobs = blobs(ELEVENTH_SOURCE, eleventh["paths"])
        if any(
            hashlib.sha256(eleventh_blobs[path]).hexdigest() != digest
            for path, digest in eleventh["paths"].items()
        ):
            return False, {}, None
        record = json.loads((root / SUCCESSOR_RECORD).read_text())
        expected = set(previous["paths"]) | PATHS
        source = record["source_sha"]
        if (
            record["base_sha"] != BASE
            or record["scope"] != "STAGE1-GAP-KB01-MASTER_V2.0"
            or set(record["paths"]) != expected
            or not ancestor(BASE, source)
            or not ancestor(ELEVENTH_SEAL, source)
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

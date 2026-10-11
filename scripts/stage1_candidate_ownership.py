"""Approved0019 finite successor, authenticated from Git blobs, never live hashes.

Historical M2-E/KB proof records and frozen migration bytes remain authoritative.
Only the explicitly enumerated R1.1 owning-contract paths may succeed those bytes.
"""

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

BASE = "df3a10923734495d728981f4f319b66afadf8c71"
RECORD = "evidence/stage1-full-e2e/r11_approved_owner_overlay.json"
OWNER_PATHS = frozenset(
    (
        ".github/workflows/stage1-candidate-governance.yml",
        "ARCHITECTURE_RULES.md",
        "alembic/env.py",
        "alembic/versions/0019_stage1_candidate_governance.py",
        "frontend/e2e/candidate-governance.spec.ts",
        "frontend/e2e/fixtures/candidate-governance.docx",
        "frontend/e2e/m2d.spec.ts",
        "frontend/e2e/phase1kb.spec.ts",
        "frontend/src/api/m2a-generated.ts",
        "frontend/src/api/m2a-schemas.json",
        "frontend/src/features/intake/CandidateReview.tsx",
        "frontend/src/features/intake/IntakeFeature.tsx",
        "frontend/src/features/intake/ProductionIntake.tsx",
        "frontend/src/features/intake/candidateApi.ts",
        "frontend/src/features/intake/candidates.test.tsx",
        "frontend/src/features/intake/persistence.ts",
        "frontend/src/locales/en-US.json",
        "frontend/src/locales/zh-CN.json",
        "frontend/src/locales/zh-HK.json",
        "scripts/architecture_rule_check.py",
        "scripts/m2e_closure.py",
        "scripts/m2a_ownership.py",
        "scripts/phase1l_b_ownership.py",
        "scripts/m2e_r1_ownership.py",
        "scripts/stage1_candidate_architecture.py",
        "scripts/stage1_candidate_closure.py",
        "scripts/stage1_candidate_ownership.py",
        "sdk/openapi/external-v1.json",
        "sdk/python/src/crossborder_agent/client.py",
        "sdk/python/src/crossborder_agent/external-v1.json",
        "sdk/typescript/src/client.ts",
        "sdk/typescript/src/generated.ts",
        "src/crossborder_compliance/application/candidate_governance_services.py",
        "src/crossborder_compliance/application/context_services.py",
        "src/crossborder_compliance/application/document_ports.py",
        "src/crossborder_compliance/application/external_channel.py",
        "src/crossborder_compliance/application/intake_services.py",
        "src/crossborder_compliance/application/llm_document_extraction.py",
        "src/crossborder_compliance/application/llm_gateway_services.py",
        "src/crossborder_compliance/application/llm_invocation_services.py",
        "src/crossborder_compliance/application/llm_model_catalog.py",
        "src/crossborder_compliance/domain/llm_gateway.py",
        "src/crossborder_compliance/domain/llm_invocation.py",
        "src/crossborder_compliance/infrastructure/external_composition.py",
        "src/crossborder_compliance/infrastructure/intake_composition.py",
        "src/crossborder_compliance/infrastructure/llm_document_inputs.py",
        "src/crossborder_compliance/infrastructure/llm_draft_document_inputs.py",
        "src/crossborder_compliance/infrastructure/llm_gateway_configuration.py",
        "src/crossborder_compliance/infrastructure/llm_invocation_governance.py",
        "src/crossborder_compliance/infrastructure/llm_snapshot_pins.py",
        "src/crossborder_compliance/infrastructure/persistence/candidate_governance.py",
        "src/crossborder_compliance/infrastructure/persistence/candidate_governance_models.py",
        "src/crossborder_compliance/infrastructure/persistence/candidate_preparation_pins.py",
        "src/crossborder_compliance/infrastructure/persistence/context_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/document_repositories.py",
        "src/crossborder_compliance/infrastructure/persistence/llm_gateway_audit.py",
        "src/crossborder_compliance/infrastructure/persistence/models.py",
        "src/crossborder_compliance/infrastructure/persistence/project_intake.py",
        "src/crossborder_compliance/infrastructure/persistence/structured_intake.py",
        "src/crossborder_compliance/interfaces/api/external_schemas.py",
        "src/crossborder_compliance/interfaces/api/routes/external.py",
        "src/crossborder_compliance/interfaces/api/routes/intake.py",
        "tests/test_m2e_r11_migrations.py",
        "tests/test_phase1kb_document_postgres.py",
        "tests/test_stage1_candidate_architecture.py",
        "tests/test_stage1_candidate_governance_domain.py",
        "tests/test_stage1_candidate_governance_http.py",
        "tests/test_stage1_candidate_governance_migrations.py",
    )
)


def overlay(root, previous_paths):
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

    def blobs(sha, paths):
        with tarfile.open(
            fileobj=io.BytesIO(git("archive", "--format=tar", sha, "--", *sorted(paths)))
        ) as archive:
            return {f.name: archive.extractfile(f).read() for f in archive if f.isfile()}

    try:
        # Re-prove both immutable historical overlay records from the formal
        # baseline and their original source commits. No historical proof edits.
        historical_paths = set()
        for path in (
            "evidence/m2e/r1_approved_owner_overlay.json",
            "evidence/m2e/resume_approved_owner_overlay.json",
        ):
            frozen = git("show", BASE + ":" + path)
            if (root / path).read_bytes() != frozen:
                return False, {}, None
            record = json.loads(frozen)
            source = record["source_sha"]
            if not ancestor(record["base_sha"], source) or not ancestor(source, BASE):
                return False, {}, None
            original = blobs(source, record["paths"])
            if not all(
                hashlib.sha256(original[p]).hexdigest() == h for p, h in record["paths"].items()
            ):
                return False, {}, None
            historical_paths.update(record["paths"])
        if historical_paths != set(previous_paths):
            return False, {}, None
        data = json.loads((root / RECORD).read_text())
        source = data["source_sha"]
        paths = OWNER_PATHS | previous_paths
        if not (
            data["base_sha"] == BASE
            and source != BASE
            and ancestor(BASE, source)
            and ancestor(source, "HEAD")
            and set(data["paths"]) == paths
        ):
            return False, {}, None
        committed = blobs(source, paths)
        valid = all(
            hashlib.sha256(committed[p]).hexdigest() == h
            and (root / p).read_bytes() == committed[p]
            for p, h in data["paths"].items()
        )
        # All existing product, test, migration, workflow and governance files
        # outside the approved finite successor retain exact formal-base bytes.
        baseline = git("ls-tree", "-r", "--name-only", BASE).decode().splitlines()
        originals = blobs(BASE, baseline)
        valid = valid and all(
            (root / p).read_bytes() == originals[p] for p in baseline if p not in OWNER_PATHS
        )
        changes = set(git("diff", "--name-only", BASE, source).decode().splitlines())
        changes |= set(git("diff", "--name-only", BASE).decode().splitlines())
        changes |= set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
        evidence = lambda p: p.startswith(("docs/stage1-e2e/", "evidence/stage1-full-e2e/"))
        valid = valid and all(
            p in OWNER_PATHS or evidence(p) or p == "Phase1H_integration_closure.md"
            for p in changes
        )
        # The pre-existing user closure file is not implementation or approval.
        user_file = root / "Phase1H_integration_closure.md"
        if user_file.exists():
            valid = (
                valid
                and hashlib.sha256(user_file.read_bytes()).hexdigest()
                == "c9530e2a9c36746deadc143e3e94ab982c370650b653758ebe2f1d1aeb19ec37"
            )
        return valid, data["paths"], source
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        return False, {}, None

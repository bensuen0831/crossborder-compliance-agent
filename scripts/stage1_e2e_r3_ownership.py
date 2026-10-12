"""Finite R3 acceptance successor; authenticate committed blobs, never live hashes."""
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

BASE = "292fc6e9e1bc58deb1ec20920c1acf43e3e9109e"
RECORD = "evidence/stage1-full-e2e/r3/approved_owner_overlay.json"
PATHS = frozenset((
    '.github/workflows/m2e-external-agent-api.yml',
    '.github/workflows/phase1a-runtime-smoke.yml',
    '.github/workflows/phase1kb-multi-provider-llm-governance.yml',
    '.github/workflows/stage1-candidate-governance.yml',
    '.github/workflows/stage1-full-e2e.yml',
    'frontend/e2e/stage1-business.spec.ts',
    'frontend/scripts/stage1/uat.py',
    'frontend/src/api/m2a-generated.ts',
    'frontend/src/api/m2a-schemas.json',
    'frontend/src/features/intake/CandidateReview.tsx',
    'frontend/src/features/intake/candidateApi.ts',
    'frontend/src/features/intake/candidates.test.tsx',
    'frontend/src/features/results/Stage1Workspace.tsx',
    'scripts/architecture_rule_check.py',
    'scripts/stage1_business_architecture.py',
    'scripts/stage1_business_closure.py',
    'scripts/stage1_e2e_ownership.py',
    'scripts/stage1_e2e_r3_ownership.py',
    'scripts/stage1_sdk_toolchain.sh',
    'sdk/openapi/external-v1.json',
    'sdk/python/src/crossborder_agent/external-v1.json',
    'sdk/typescript/src/generated.ts',
    'src/crossborder_compliance/application/intake_services.py',
    'src/crossborder_compliance/infrastructure/intake_composition.py',
    'src/crossborder_compliance/infrastructure/persistence/project_intake.py',
    'src/crossborder_compliance/interfaces/api/routes/classification.py',
    'src/crossborder_compliance/interfaces/api/routes/country_compliance.py',
    'tests/e2e/stage1/business_cases/TC-01.json',
    'tests/e2e/stage1/business_cases/TC-02.json',
    'tests/e2e/stage1/business_cases/TC-03.json',
    'tests/e2e/stage1/business_cases/TC-04.json',
    'tests/e2e/stage1/typescript-business.mjs',
    'tests/stage1_business_fixtures.py',
    'tests/stage1_business_manifest.py',
    'tests/stage1_external_business.py',
    'tests/stage1_formal_acceptance.py',
    'tests/stage1_semantic_parity.py',
    'tests/test_stage1_business_http.py',
    'tests/test_stage1_channel_parity.py',
    'tests/test_stage1_r3_architecture.py',
    'tests/test_stage1_r3_intake_projection.py',
    'tests/test_stage1_r3_llm_rag.py',
    'tests/test_stage1_r3_owned_result_reads.py',
    'tests/test_stage1_r3_sdk_business.py',
    'tests/test_stage1_r3_semantic_parity.py',
    'tests/test_stage1_r3_temporal_business.py',
))

def overlay(root):
    root = Path(root).resolve()
    def git(*args):
        return subprocess.check_output(["git", "-c", "core.quotepath=false", *args], cwd=root, stderr=subprocess.DEVNULL)
    def ancestor(a, b):
        return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=root, stderr=subprocess.DEVNULL).returncode == 0
    def blobs(sha, paths):
        with tarfile.open(fileobj=io.BytesIO(git("archive", sha, "--", *sorted(paths)))) as tar:
            return {f.name: tar.extractfile(f).read() for f in tar if f.isfile()}
    try:
        previous_path = "evidence/stage1-full-e2e/r2/approved_owner_overlay.json"
        previous_bytes = git("show", BASE + ":" + previous_path)
        if (root / previous_path).read_bytes() != previous_bytes:
            return False, {}, None
        previous = json.loads(previous_bytes)
        previous_blobs = blobs(previous["source_sha"], previous["paths"])
        if not ancestor(previous["source_sha"], BASE) or any(hashlib.sha256(previous_blobs[p]).hexdigest() != h for p, h in previous["paths"].items()):
            return False, {}, None
        record = json.loads((root / RECORD).read_text())
        source = record["source_sha"]
        expected = set(previous["paths"]) | PATHS
        if record["base_sha"] != BASE or set(record["paths"]) != expected or not ancestor(BASE, source) or not ancestor(source, "HEAD"):
            return False, {}, None
        committed = blobs(source, expected)
        if any(hashlib.sha256(committed[p]).hexdigest() != h or (root / p).read_bytes() != committed[p] for p, h in record["paths"].items()):
            return False, {}, None
        baseline_paths = git("ls-tree", "-r", "--name-only", BASE).decode().splitlines()
        originals = blobs(BASE, baseline_paths)
        if any((root / p).read_bytes() != originals[p] for p in baseline_paths if p not in PATHS):
            return False, {}, None
        delta = set(git("diff", "--name-only", BASE, source).decode().splitlines()) | set(git("diff", "--name-only", BASE).decode().splitlines()) | set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
        if any(p not in PATHS and not p.startswith(("docs/stage1-e2e/", "evidence/stage1-full-e2e/r3/")) and p != "Phase1H_integration_closure.md" for p in delta):
            return False, {}, None
        user = root / "Phase1H_integration_closure.md"
        if user.exists() and hashlib.sha256(user.read_bytes()).hexdigest() != "c9530e2a9c36746deadc143e3e94ab982c370650b653758ebe2f1d1aeb19ec37":
            return False, {}, None
        return True, record["paths"], source
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError):
        return False, {}, None

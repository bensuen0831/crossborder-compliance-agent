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
    ".github/workflows/phase1a-runtime-smoke.yml",
    ".github/workflows/phase1kb-multi-provider-llm-governance.yml",
    "scripts/stage1_e2e_ownership.py",
    "scripts/stage1_e2e_r3_ownership.py",
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

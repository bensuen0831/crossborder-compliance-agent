#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export LANGGRAPH_STRICT_MSGPACK=true
export EVIDENCE_DIR="${EVIDENCE_DIR:-$ROOT/artifacts/phase1a-runtime}"
mkdir -p "$EVIDENCE_DIR"
LOG="$EVIDENCE_DIR/ci_complete.log"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

finish() {
  rc=$?
  python smoke/ci_run_evidence.py || true
  if [[ $rc -ne 0 ]]; then
    echo "PHASE1A_RUNTIME_GATE_EXIT_CODE=$rc"
  fi
  exit $rc
}
trap finish EXIT

echo "=== Phase 1A.1 preflight ==="
python smoke/preflight.py | tee "$EVIDENCE_DIR/preflight.json"

echo "=== Real PostgreSQL domain migration ==="
alembic upgrade head | tee "$EVIDENCE_DIR/alembic_upgrade.log"

echo "=== Post-Alembic schema proof (before LangGraph setup) ==="
python smoke/postgres_schema_evidence.py --phase post-alembic | tee "$EVIDENCE_DIR/post_alembic_schema.json"

echo "=== Runtime versions ==="
python smoke/runtime_versions.py

echo "=== Process 1: start -> checkpoint -> interrupt -> exit ==="
python smoke/smoke_start.py | tee "$EVIDENCE_DIR/process1.log"

echo "=== Process 2: fresh process -> checkpoint load -> Command(resume) -> complete ==="
python smoke/smoke_resume.py | tee "$EVIDENCE_DIR/process2.log"

echo "=== Process 3: duplicate client retry after completion ==="
python smoke/smoke_resume_retry.py | tee "$EVIDENCE_DIR/process3_resume_retry.log"

echo "=== Post-runtime checkpointer schema proof ==="
python smoke/postgres_schema_evidence.py --phase post-runtime | tee "$EVIDENCE_DIR/post_runtime_schema.json"

echo "=== Mandatory DB/runtime assertions ==="
python smoke/smoke_verify.py | tee "$EVIDENCE_DIR/runtime_verify.json"

echo "=== Full test suite; runtime tests are INCLUDED and may not skip ==="
set +e
pytest -q 2>&1 | tee "$EVIDENCE_DIR/pytest_full.log"
pytest_rc=${PIPESTATUS[0]}
set -e
{
  echo "# Phase 1A.1 Test Result"
  echo
  if [[ $pytest_rc -eq 0 ]]; then echo "**Decision: PASS**"; else echo "**Decision: FAIL**"; fi
  echo
  echo '~~~text'
  cat "$EVIDENCE_DIR/pytest_full.log"
  echo '~~~'
} > "$EVIDENCE_DIR/test_result.md"
if [[ $pytest_rc -ne 0 ]]; then exit $pytest_rc; fi

echo "=== Architecture rule check ==="
python scripts/architecture_rule_check.py | tee "$EVIDENCE_DIR/architecture_rule_check_stdout.json"

echo "=== Gate complete ==="
echo "Phase 1A Mandatory Runtime Gate = PASS"

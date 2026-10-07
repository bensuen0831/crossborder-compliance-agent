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

echo "=== Phase 1B domain schema + source-of-truth verification ==="
python scripts/phase1b_schema_check.py | tee "$EVIDENCE_DIR/phase1b_schema_check.json"

echo "=== Phase 1C metadata / registry / security schema verification ==="
python scripts/phase1c_schema_check.py | tee "$EVIDENCE_DIR/phase1c_schema_check.json"

echo "=== Phase 1D document intelligence schema verification ==="
python scripts/phase1d_schema_check.py | tee "$EVIDENCE_DIR/phase1d_schema_check.json"

echo "=== Phase 1E context resolution schema verification ==="
python scripts/phase1e_schema_check.py | tee "$EVIDENCE_DIR/phase1e_schema_check.json"

echo "=== Phase 1F knowledge / ingestion / scope schema verification ==="
python scripts/phase1f_schema_check.py | tee "$EVIDENCE_DIR/phase1f_schema_check.json"

echo "=== Phase 1G retrieval / sufficiency / external evidence schema verification ==="
python scripts/phase1g_schema_check.py | tee "$EVIDENCE_DIR/phase1g_schema_check.json"

echo "=== Phase 1H safe rule / formal classification schema verification ==="
python scripts/phase1h_schema_check.py | tee "$EVIDENCE_DIR/phase1h_schema_check.json"

echo "=== Phase1I country/scenario/applicability schema verification ==="
python scripts/phase1i_schema_check.py | tee "$EVIDENCE_DIR/phase1i_schema_check.json"

echo "=== Phase1J formal decision schema verification ==="
python scripts/phase1j_schema_check.py | tee "$EVIDENCE_DIR/phase1j_schema_check.json"

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
pytest -q --junitxml="$EVIDENCE_DIR/pytest_full.xml" 2>&1 | tee "$EVIDENCE_DIR/pytest_full.log"
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
python scripts/verify_full_pytest.py "$EVIDENCE_DIR"

echo "=== Architecture rule check ==="
python scripts/architecture_rule_check.py | tee "$EVIDENCE_DIR/architecture_rule_check_stdout.json"

echo "=== Additive M2-A boundaries ==="
python scripts/m2a_ownership.py | tee "$EVIDENCE_DIR/m2a_ownership.json"
python scripts/m2a_architecture_check.py | tee "$EVIDENCE_DIR/m2a_architecture_check.json"
python scripts/phase1k_a_boundary_check.py | tee "$EVIDENCE_DIR/phase1k_a_boundary.json"
python scripts/stage1_alpha_integrity.py | tee "$EVIDENCE_DIR/stage1_integrity.json"

echo "=== Additive M2-B boundaries ==="
python scripts/m2b_architecture_check.py | tee "$EVIDENCE_DIR/m2b_architecture_check.json"

echo "=== Gate complete ==="
echo "Phase 1A Mandatory Runtime Gate = PASS"
echo "Phase 1B PostgreSQL Regression Gate = PASS"
echo "Phase 1C Metadata / Registry Foundation Gate = PASS"
echo "Phase 1D Document Intelligence Foundation Gate = PASS"
echo "Phase 1E Context Resolution / Formal Data Inventory / Data Flow Gate = PASS"
echo "Phase 1F Knowledge Ingestion / Scope Resolver Foundation Gate = PASS"

echo "Phase 1G Scope-first Retrieval / Evidence Foundation Gate = PASS"
echo "Phase 1H Safe Rule Engine / Formal Classification Gate = PASS"

echo "Phase1I Applicability / Country / Scenario Gate = PASS"
echo "Phase1J Formal Decision Gate = PASS"

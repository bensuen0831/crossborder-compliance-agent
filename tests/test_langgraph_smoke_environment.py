from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import pytest
from crossborder_compliance.config import get_settings

@pytest.mark.runtime_smoke
def test_phase1a_mandatory_runtime_environment_is_real_and_ready():
    missing=[mod for mod in ["langgraph","psycopg","redis"] if importlib.util.find_spec(mod) is None]
    assert not missing, f"missing mandatory runtime modules: {missing}"
    import psycopg, redis
    settings=get_settings()
    with psycopg.connect(settings.langgraph_database_uri) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1"); assert cur.fetchone()[0]==1
            cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
            row=cur.fetchone(); assert row is not None and row[0]
    assert redis.Redis.from_url(settings.redis_url).ping() is True

@pytest.mark.runtime_smoke
def test_phase1a_runtime_smoke_empirical_evidence_is_complete():
    state_file=Path(os.environ.get("SMOKE_STATE_FILE","/tmp/phase1a_smoke_ids.json"))
    assert state_file.exists(), "mandatory two-process smoke state file is missing"
    import json, psycopg
    ids=json.loads(state_file.read_text(encoding="utf-8"))
    assert ids.get("process1_checkpoint_row_count",0)>0
    assert ids.get("process2_checkpoint_context_preserved") is True
    assert ids.get("resume_retry_safe") is True
    settings=get_settings()
    with psycopg.connect(settings.langgraph_database_uri) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM checkpoints WHERE thread_id=%s",(ids["workflow_run_id"],)); assert cur.fetchone()[0]>0
            cur.execute("SELECT status, thread_id, analysis_snapshot_id, tenant_id FROM workflow_runs WHERE workflow_run_id=%s",(ids["workflow_run_id"],))
            assert cur.fetchone()==("COMPLETED",ids["workflow_run_id"],ids["analysis_snapshot_id"],ids["tenant_id"])
            cur.execute("SELECT count(*) FROM review_tasks WHERE workflow_run_id=%s",(ids["workflow_run_id"],)); assert cur.fetchone()[0]==1
            cur.execute("SELECT event_type, count(*) FROM workflow_events WHERE workflow_run_id=%s GROUP BY event_type",(ids["workflow_run_id"],))
            counts=dict(cur.fetchall())
            assert counts.get("REVIEW_REQUIRED")==1
            assert counts.get("WORKFLOW_RESUMED")==1
            assert counts.get("WORKFLOW_COMPLETED")==1

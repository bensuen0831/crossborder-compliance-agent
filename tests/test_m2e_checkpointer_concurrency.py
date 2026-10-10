"""Parallel first startup and fresh-process official saver initialization."""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row

from crossborder_compliance.workflows.langgraph_adapter import LangGraphWorkflowRuntimeAdapter

pytestmark = pytest.mark.runtime_smoke


def test_parallel_first_startup_and_process_restart_one_checkpoint_authority():
    uri = os.environ["LANGGRAPH_DATABASE_URI"]
    schema = "m2e_checkpoint_" + uuid4().hex
    with psycopg.connect(uri, autocommit=True) as c:
        c.execute(f"CREATE SCHEMA {schema}")
    barrier = Barrier(3)

    def initialize(_):
        with psycopg.connect(
            uri, options=f"-c search_path={schema}", autocommit=True, row_factory=dict_row
        ) as c:
            barrier.wait(timeout=10)
            LangGraphWorkflowRuntimeAdapter._setup_checkpointer(PostgresSaver(c))
            return c.execute("select count(*) as count from checkpoint_migrations").fetchone()[
                "count"
            ]

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            counts = list(pool.map(initialize, range(3)))
        assert len(set(counts)) == 1 and counts[0] > 0
        script = """import os, psycopg
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver
from crossborder_compliance.workflows.langgraph_adapter import LangGraphWorkflowRuntimeAdapter
with psycopg.connect(
    os.environ['LANGGRAPH_DATABASE_URI'],
    options='-c search_path='+os.environ['M2E_CHECKPOINT_SCHEMA'],
    autocommit=True, row_factory=dict_row
) as c:
    LangGraphWorkflowRuntimeAdapter._setup_checkpointer(PostgresSaver(c))
    print(c.execute('select count(*) as count from checkpoint_migrations').fetchone()['count'])
"""
        result = subprocess.run(
            [os.sys.executable, "-c", script],
            env={**os.environ, "M2E_CHECKPOINT_SCHEMA": schema},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, "fresh process saver initialization failed"
        assert int(result.stdout.strip()) == counts[0]
    finally:
        with psycopg.connect(uri, autocommit=True) as c:
            c.execute(f"DROP SCHEMA {schema} CASCADE")

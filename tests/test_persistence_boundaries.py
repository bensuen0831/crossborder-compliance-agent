from sqlalchemy import create_engine, inspect
from crossborder_compliance.infrastructure.persistence.models import Base
def test_idempotency_tables_separate_and_no_langgraph_tables_in_domain_metadata():
    engine=create_engine("sqlite+pysqlite:///:memory:"); Base.metadata.create_all(engine); tables=set(inspect(engine).get_table_names())
    assert "execution_idempotency_records" in tables and "api_idempotency_records" in tables
    assert "checkpoints" not in tables and "checkpoint_writes" not in tables
def test_analysis_snapshot_is_domain_table():
    assert "analysis_snapshots" in Base.metadata.tables

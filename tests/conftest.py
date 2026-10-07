"""Release test-owned canonical SQLAlchemy pools without changing DB semantics.

Expanded real-PG workflow tests create several independently composed readers.
All use the original factory and real transactions; only idle connections are
released after fixture teardown. Domain rows/checkpoints are never removed.
"""

import pytest


@pytest.fixture(autouse=True)
def release_test_owned_database_pools(monkeypatch):
    from crossborder_compliance.infrastructure.persistence import db

    original = db.build_engine
    engines = []

    def tracked(database_url):
        engine = original(database_url)
        engines.append(engine)
        return engine

    monkeypatch.setattr(db, "build_engine", tracked)
    yield
    for engine in reversed(engines):
        engine.dispose()

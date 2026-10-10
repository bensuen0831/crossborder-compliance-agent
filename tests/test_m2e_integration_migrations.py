"""Northbound populated downgrade refuses without losing identity/revocation audit."""

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_phase1c_model_registry import _seed_tenant
from test_phase1h_migrations import migrate
from test_phase1j_migrations import catalog

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.integrations import (
    ClientCreate,
    IntegrationPolicy,
    IntegrationScope,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.integrations import (
    PostgresIntegrationRepository,
)

pytestmark = pytest.mark.runtime_smoke
ROOT = Path(__file__).resolve().parents[1]
OLD = "0016_phase1kb_multi_provider_llm_governance"
MID = "0017_m2e_external_agent_api"


def test_empty_and_populated_integration_downgrade_transactional_policy():
    name = "m2e_credentials_migration_" + uuid4().hex
    base = make_url(get_settings().database_url)
    url = base.set(database=name).render_as_string(hide_password=False)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    engine = None
    try:
        assert migrate(ROOT, url, "upgrade", MID).returncode == 0
        schema = catalog(url)
        assert migrate(ROOT, url, "downgrade", OLD).returncode == 0
        assert migrate(ROOT, url, "upgrade", MID).returncode == 0
        assert catalog(url) == schema
        engine, sf = build_session_factory(url)
        tenant = uuid4()
        _seed_tenant(sf, tenant)
        ctx = RepositoryContext.user(tenant, "migration-admin", {"integration:manage"})
        PostgresIntegrationRepository(sf, IntegrationPolicy(), ctx).create_client(
            ClientCreate(
                display_name="Durable enterprise identity",
                allowed_scopes=(IntegrationScope.PROJECT_READ,),
            ),
            uuid4().hex,
        )

        def stored():
            with engine.connect() as c:
                return list(
                    c.execute(
                        text(
                            "select credential_id,credential_hash,status "
                            "from integration_credentials order by credential_id"
                        )
                    ).tuples()
                )

        before = stored()
        refusal = migrate(ROOT, url, "downgrade", OLD)
        assert refusal.returncode != 0 and "M2-E integration records retained" in refusal.stderr
        assert stored() == before and catalog(url) == schema
        with engine.connect() as c:
            assert c.scalar(text("select version_num from alembic_version")) == MID
        assert migrate(ROOT, url, "upgrade", "head").returncode == 0
        assert stored() == before
        out = Path(os.getenv("EVIDENCE_DIR", str(ROOT / "artifacts/m2e")))
        out.mkdir(parents=True, exist_ok=True)
        (out / "integration_migration_measured.json").write_text(
            json.dumps(
                {
                    "empty0017_downgrade_reupgrade": True,
                    "populated0017_transactional_refusal": True,
                    "credential_identity_hash_status_preserved": True,
                    "0018_upgrade_preserves_integration_identity": True,
                },
                indent=2,
            )
            + "\n"
        )
    finally:
        if engine:
            engine.dispose()
        with admin.connect() as c:
            c.execute(
                text("select pg_terminate_backend(pid) from pg_stat_activity where datname=:n"),
                {"n": name},
            )
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()

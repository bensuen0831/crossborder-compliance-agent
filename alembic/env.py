from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from crossborder_compliance.infrastructure.persistence import (
    context_models as _context_models,  # noqa: F401
)
from crossborder_compliance.infrastructure.persistence import (
    decision_models as _decision_models,  # noqa: F401
)
from crossborder_compliance.infrastructure.persistence import (
    document_models as _document_models,  # noqa: F401
)
from crossborder_compliance.infrastructure.persistence import (
    metadata_models as _metadata_models,  # noqa: F401
)
from crossborder_compliance.infrastructure.persistence import (
    review_models as _review_models,  # noqa: F401
)
from crossborder_compliance.infrastructure.persistence.models import Base
from crossborder_compliance.infrastructure.persistence import knowledge_management_models as _knowledge_management_models  # noqa: F401
from crossborder_compliance.infrastructure.persistence import knowledge_upload_models as _knowledge_upload_models  # noqa: F401
from crossborder_compliance.infrastructure.persistence import knowledge_manifest_models as _knowledge_manifest_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
url = os.getenv("DATABASE_URL")
if url:
    config.set_main_option("sqlalchemy.url", url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

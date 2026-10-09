"""Opt-in acceptance of already governed providers; outputs only sanitized probe status."""

import argparse
import json
import os
from uuid import UUID

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.llm_provider_inspection import ProviderInspection
from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.model_control import (
    PostgresModelControlRepository,
)


def main():
    if os.environ.get("REAL_LLM_E2E") != "1":
        raise SystemExit("Explicit REAL_LLM_E2E=1 required; mandatory CI uses local providers")
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--provider-version-id", type=UUID, action="append", default=[])
    parser.add_argument("--deployment-id", type=UUID, action="append", default=[])
    args = parser.parse_args()
    if not args.provider_version_id or not args.deployment_id:
        raise SystemExit("Supply governed provider/model identities provisioned through Admin")
    context = RepositoryContext.user(
        args.tenant_id, "opt-in-provider-acceptance", {"metadata:admin"}
    )
    _, sessions = build_session_factory(get_settings().database_url)
    secrets = EncryptedFileSecretStore(
        os.environ["LLM_SECRET_STORE_ROOT"],
        os.environ["LLM_SECRET_STORE_KEY"].encode(),
        args.tenant_id,
    )
    probe = ProviderInspection(PostgresModelControlRepository(sessions, context), secrets)
    results = []
    for identity in args.provider_version_id:
        results.append(
            {
                "provider_version_id": str(identity),
                "status": probe.connection_test(identity)["status"],
            }
        )
    for identity in args.deployment_id:
        results.append(
            {"deployment_id": str(identity), "status": probe.model_test(identity, "chat")["status"]}
        )
    print(json.dumps({"opt_in": True, "results": results}, indent=2))
    raise SystemExit(any(r["status"] != "HEALTHY" for r in results))


if __name__ == "__main__":
    main()

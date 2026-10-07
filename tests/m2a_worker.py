"""Fresh-process canonical START/READ using current host grants and durable refs."""

import json
import sys
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.workflow import router

if __name__ == "__main__":
    manifest = json.loads(Path(sys.argv[1]).read_text())
    context = RepositoryContext.user(UUID(manifest["tenant"]), "author", set(manifest["scopes"]))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_repository_context] = lambda: context
    with TestClient(app) as client:
        started = client.post(
            f"/api/v1/projects/{manifest['project']}/snapshots/{manifest['snapshot']}/workflow",
            json={},
        )
        assert started.status_code == 200, started.text
        result = started.json()
        read = client.get(f"/api/v1/workflows/{result['workflow_run_id']}")
        assert read.status_code == 200 and read.json() == result, read.text
    print(json.dumps(result))

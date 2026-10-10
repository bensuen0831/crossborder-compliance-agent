"""Export gateway contracts from canonical routes; no business model duplication."""

import json
from pathlib import Path

from fastapi import FastAPI

from crossborder_compliance.interfaces.api.external_openapi import external_openapi
from crossborder_compliance.interfaces.api.routes.integrations import admin_router

root = Path(__file__).resolve().parents[3]
app = FastAPI(title="Integration Admin contract", version="1.0.0")
app.include_router(admin_router)
admin = app.openapi()
output = root / "frontend/src/api/m2e-schemas.json"
output.write_text(json.dumps(admin, indent=2) + "\n")
public = root / "sdk/openapi/external-v1.json"
public.parent.mkdir(parents=True, exist_ok=True)
public.write_text(json.dumps(external_openapi(), indent=2) + "\n")
(root / "sdk/python/src/crossborder_agent/external-v1.json").write_text(public.read_text())

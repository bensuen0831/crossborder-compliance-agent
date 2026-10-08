"""Export owned schemas from canonical API; generated types use existing toolchain."""

import json
from pathlib import Path

from fastapi import FastAPI

from crossborder_compliance.interfaces.api.routes.model_providers import router
from crossborder_compliance.interfaces.api.routes.model_providers import bindings_router
from crossborder_compliance.interfaces.api.routes.llm_models import router as llm_models_router

app = FastAPI()
app.include_router(router)
app.include_router(bindings_router)
app.include_router(llm_models_router)
output = Path(__file__).resolve().parents[2] / "src/api/phase1kb-schemas.json"
output.write_text(json.dumps(app.openapi(), indent=2) + "\n")

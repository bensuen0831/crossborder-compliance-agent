"""Export owned schemas from canonical API; generated types use existing toolchain."""

import json
from pathlib import Path

from fastapi import FastAPI

from crossborder_compliance.interfaces.api.routes.model_providers import router

app = FastAPI()
app.include_router(router)
output = Path(__file__).resolve().parents[2] / "src/api/phase1kb-schemas.json"
output.write_text(json.dumps(app.openapi(), indent=2) + "\n")

"""Generate typed review transport from the canonical backend contracts."""

import json
from pathlib import Path

from fastapi import FastAPI

from crossborder_compliance.interfaces.api.routes.reviews import router

app = FastAPI()
app.include_router(router)
output = Path(__file__).resolve().parents[2] / "src/api/m2d-schemas.json"
output.write_text(json.dumps(app.openapi(), indent=2) + "\n")

"""Generate the intake transport contract from its canonical backend DTOs."""

import json
from pathlib import Path

from fastapi import FastAPI

from crossborder_compliance.interfaces.api.routes.intake import router
from crossborder_compliance.interfaces.api.routes.intake_documents import router as document_router

app = FastAPI()
app.include_router(router)
app.include_router(document_router)
output = Path(__file__).resolve().parents[2] / "src/api/m2a-schemas.json"
output.write_text(json.dumps(app.openapi(), indent=2) + "\n")

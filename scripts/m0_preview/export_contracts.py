"""Export the frozen backend OpenAPI; no replacement domain or legal schema."""
import json
from pathlib import Path

from crossborder_compliance.interfaces.api.main import app

root = Path(__file__).resolve().parents[2]
output = root / "frontend/src/api/openapi.json"
output.parent.mkdir(parents=True, exist_ok=True)
spec = app.openapi()
# Only consume existing M0 endpoints; include their exact transitive schemas.
paths = {
    path: value for path, value in spec["paths"].items()
    if path in {
        "/api/v1/projects/{project_id}/knowledge/retrieve",
        "/api/v1/projects/{project_id}/knowledge-scope",
        "/api/v1/retrieval-runs/{id}", "/api/v1/evidence-packs/{id}",
        "/api/v1/knowledge-sufficiency/{id}",
        "/api/v1/admin/knowledge-versions/{id}/runtime-readiness",
        "/api/v1/metadata/products", "/api/v1/metadata/scenarios",
        "/api/v1/metadata/jurisdictions", "/health/ready",
    }
}
schemas = {}


def collect(value):
    if isinstance(value, dict):
        ref = value.get("$ref", "")
        if ref.startswith("#/components/schemas/"):
            name = ref.rsplit("/", 1)[1]
            if name not in schemas:
                schemas[name] = spec["components"]["schemas"][name]
                collect(schemas[name])
        for item in value.values():
            collect(item)
    elif isinstance(value, list):
        for item in value:
            collect(item)


collect(paths)
output.write_text(json.dumps({
    "openapi": spec["openapi"], "info": spec["info"],
    "paths": paths, "components": {"schemas": schemas},
}, ensure_ascii=False, indent=2) + "\n")
print(f"Exported {output.relative_to(root)} from the existing FastAPI routers")

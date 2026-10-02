"""Export the frozen backend OpenAPI; no replacement domain or legal schema."""
import json
from pathlib import Path

from crossborder_compliance.interfaces.api.main import app

root = Path(__file__).resolve().parents[2]
output = root / "frontend/src/api/openapi.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n")
print(f"Exported {output.relative_to(root)} from the existing FastAPI routers")

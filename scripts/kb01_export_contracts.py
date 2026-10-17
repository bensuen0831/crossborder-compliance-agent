"""Generate the management channel contract from canonical FastAPI route schemas."""

import json
from pathlib import Path

from crossborder_compliance.interfaces.api.main import app


def export(root: Path):
    spec = app.openapi()
    paths = {
        k: v
        for k, v in spec["paths"].items()
        if k.startswith("/api/v1/admin/knowledge-management/")
    }
    schemas = {}

    def collect(value):
        if isinstance(value, dict):
            reference = value.get("$ref", "")
            if reference.startswith("#/components/schemas/"):
                name = reference.rsplit("/", 1)[1]
                if name not in schemas:
                    schemas[name] = spec["components"]["schemas"][name]
                    collect(schemas[name])
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(paths)
    target = root / "frontend/src/api/kb01-openapi.json"
    target.write_text(
        json.dumps(
            {
                "openapi": spec["openapi"],
                "info": spec["info"],
                "paths": paths,
                "components": {"schemas": schemas},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    export(Path(__file__).resolve().parents[1])

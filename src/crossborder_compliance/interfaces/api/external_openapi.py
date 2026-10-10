"""Public contract projection; contains no internal/admin route or new service."""

from fastapi import FastAPI

from crossborder_compliance.domain.integrations import ExternalWorkflowEvent, GatewayError


def external_openapi():
    # Import subscriptions before including the canonical external router.
    from crossborder_compliance.interfaces.api.routes import integrations  # noqa: F401
    from crossborder_compliance.interfaces.api.routes.external import router

    projection = FastAPI(title="Cross-border Agent External Integration API", version="1.0.0")
    projection.include_router(router)
    spec = projection.openapi()
    schemas = spec["components"]["schemas"]
    schemas["GatewayError"] = GatewayError.model_json_schema()
    schemas["ExternalWorkflowEvent"] = ExternalWorkflowEvent.model_json_schema()
    spec["components"]["securitySchemes"] = {
        "IntegrationBearer": {
            "type": "http",
            "scheme": "bearer",
            "description": "Short-lived OAuth token or revocable service credential.",
        },
        "ClientCredentials": {
            "type": "oauth2",
            "flows": {
                "clientCredentials": {
                    "tokenUrl": "/api/v1/external/oauth/token",
                    "scopes": {
                        x.value: x.value
                        for x in __import__(
                            "crossborder_compliance.domain.integrations",
                            fromlist=["IntegrationScope"],
                        ).IntegrationScope
                    },
                }
            },
        },
    }
    for path, item in spec["paths"].items():
        for operation in item.values():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            operation["security"] = (
                [] if path.endswith("/oauth/token") else [{"IntegrationBearer": []}]
            )
            for code in ("401", "403", "404", "409", "413", "422", "429", "503", "504"):
                operation["responses"][code] = {
                    "description": "Stable sanitized gateway error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/GatewayError"}
                        }
                    },
                }
            operation["responses"].get("200", operation["responses"].get("202", {})).setdefault(
                "headers", {}
            )["X-Correlation-ID"] = {"schema": {"type": "string"}}
    # Runtime form validation forbids extra fields; reflect it in public schema.
    for name, value in schemas.items():
        if name.startswith("Body_"):
            value["additionalProperties"] = False
            if "client_secret" in value.get("properties", {}):
                value["properties"]["client_secret"].update(
                    {"writeOnly": True, "format": "password"}
                )
    spec["x-websocket"] = {
        "path": "/api/v1/external/ws/workflows/{run_id}",
        "authentication": "Authorization: Bearer (header only)",
        "resume": "Last-Event-ID header",
        "payload": {"$ref": "#/components/schemas/ExternalWorkflowEvent"},
    }
    spec["x-schema-version"] = "1.0"
    return spec

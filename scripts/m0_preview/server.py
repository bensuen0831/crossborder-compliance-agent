"""Loopback-only synthetic UAT identity adapter around unchanged Phase 1G routers.

No client tenant/scope headers are trusted. Not a production authentication service.
"""

import argparse
import json
import os
import secrets
import time
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict

from crossborder_compliance.domain.security import RepositoryContext


def create_demo_app(manifest_path: Path):
    if os.environ.get("M0_LOCAL_UAT") != "1":
        raise RuntimeError("Explicit M0_LOCAL_UAT=1 required; production auth is not supplied")
    manifest = json.loads(manifest_path.read_text())
    from crossborder_compliance.interfaces.api import main as baseline

    app = FastAPI(title="M0 Local UAT", lifespan=baseline.lifespan)
    for router in (
        baseline.health_router,
        baseline.metadata_router,
        baseline.admin_metadata_router,
        baseline.documents_router,
        baseline.context_resolution_router,
        baseline.classification_router,
        baseline.model_providers_router,
        baseline.bindings_router,
        baseline.llm_models_router,
        baseline.knowledge_router,
        baseline.retrieval_router,
    ):
        app.include_router(router)

    # Server-owned synthetic project persona strips all admin scopes. No browser grants.
    manifest["PROJECT"] = {
        **manifest["A"],
        "display_name": "UAT Project User",
        "permissions": [
            p
            for p in manifest["A"]["permissions"]
            if p not in {"knowledge:admin", "metadata:admin", "metadata:review", "metadata:publish"}
        ],
    }
    sessions = {}

    def resolve(request):
        token = request.cookies.get("m0_session")
        entry = sessions.get(token)
        if not entry or time.monotonic() - entry[1] > 3600:
            raise HTTPException(401, "trusted local UAT session required")
        return token, manifest[entry[0]]

    def presentation(token, persona):
        result = {
            "identity_key": sessions[token][2],
            "display_name": persona["display_name"],
            "tenant_label": persona["tenant_label"],
            "organization_label": None,
            "department_label": None,
            "permissions": persona["permissions"],
            "contexts": persona["contexts"],
            "demo": True,
        }
        scopes = persona["permissions"]
        grants = {}
        if "knowledge:admin" in scopes:
            grants["knowledge-versions"] = [
                "VIEW",
                "EDIT",
                "REVIEW",
                "APPROVE",
                "PUBLISH",
                "ARCHIVE",
                "OPERATIONS",
            ]
        if "metadata:admin" in scopes:
            for resource in (
                "jurisdictions",
                "scenarios",
                "products",
                "knowledge-collections",
                "templates",
                "prompts",
                "models",
                "rules",
            ):
                grants[resource] = ["VIEW", "EDIT", "REVIEW"]
                if "metadata:review" in scopes:
                    grants[resource].append("APPROVE")
                if "metadata:publish" in scopes:
                    grants[resource].extend(["PUBLISH", "ARCHIVE"])
        if grants:
            result["admin_context"] = {
                "actorId": persona["actor_id"],
                "tenantId": persona["tenant_id"],
                "roles": ["local-uat-admin"],
                "grants": grants,
                "backendScopes": scopes,
            }
        return result

    @app.middleware("http")
    async def trusted_session(request: Request, call_next):
        # Prevent exposure by accidentally running the UAT adapter on a public bind.
        if not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            return Response(status_code=403)
        host = request.headers.get("host", "").split(":", 1)[0]
        origin = request.headers.get("origin")
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            return Response(status_code=403)
        if origin:
            from urllib.parse import urlsplit

            if urlsplit(origin).netloc != request.headers.get("host"):
                return Response(status_code=403)
        try:
            _, persona = resolve(request)
            request.state.repository_context = RepositoryContext.user(
                UUID(persona["tenant_id"]), persona["actor_id"], set(persona["permissions"])
            )
        except HTTPException:
            pass  # Existing routers enforce trusted-context authorization.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    class Login(BaseModel):
        model_config = ConfigDict(extra="forbid")
        persona: str

    @app.post("/m0-demo/login")
    def login(payload: Login, request: Request, response: Response):
        if payload.persona not in manifest:
            raise HTTPException(403, "unknown local UAT persona")
        old = request.cookies.get("m0_session")
        sessions.pop(old, None)
        token = secrets.token_urlsafe(32)
        sessions[token] = (payload.persona, time.monotonic(), uuid4().hex)
        response.set_cookie("m0_session", token, httponly=True, samesite="strict", max_age=3600)
        return presentation(token, manifest[payload.persona])

    @app.get("/m0-demo/session")
    def session(request: Request):
        token, persona = resolve(request)
        return presentation(token, persona)

    @app.post("/m0-demo/logout")
    def logout(request: Request, response: Response):
        sessions.pop(request.cookies.get("m0_session"), None)
        response.delete_cookie("m0_session")
        return {"status": "signed_out"}

    return app


def main():
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    uvicorn.run(create_demo_app(args.manifest), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()

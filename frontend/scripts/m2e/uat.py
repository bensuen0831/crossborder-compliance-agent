"""Extend the existing loopback UAT host; real Admin/storage/callback services."""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import UUID

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore
from crossborder_compliance.infrastructure.persistence.integration_models import (
    WebhookDeliveryEntity,
    WebhookSubscriptionEntity,
)
from crossborder_compliance.infrastructure.webhook_http import verify_signature
from crossborder_compliance.interfaces.api.routes.external import router
from crossborder_compliance.interfaces.api.routes.integrations import admin_router
from frontend.scripts.phase1kb import uat as baseline

_seed = baseline.seed
_host = baseline.create_host


def seed(args, urls, key):
    _seed(args, urls, key)
    people = json.loads(args.manifest.read_text())
    people["INTEGRATION_ADMIN"] = {
        **people["LLM_ADMIN"],
        "actor_id": "integration-admin",
        "permissions": sorted(set(people["LLM_ADMIN"]["permissions"]) | {"integration:manage"}),
        "callback_url": "http://127.0.0.1:9110/callback",
    }
    args.manifest.write_text(json.dumps(people, indent=2) + "\n")


def create_host(path):
    app = _host(path)
    previous = len(app.router.routes)
    app.include_router(admin_router)
    # Match production composition: specific control plane precedes generic
    # metadata /admin/{kind} routes in the reused loopback-only fixture host.
    app.router.routes = app.router.routes[previous:] + app.router.routes[:previous]
    app.include_router(router)
    root = os.environ["INTEGRATION_SECRET_STORE_ROOT"]
    key_file = Path(os.environ["M2E_UAT_KEY_FILE"])
    key = key_file.read_bytes()
    app.state.integration_secret_store_factory = lambda ctx: EncryptedFileSecretStore(
        root, key, ctx.tenant_id
    )
    app.state.integration_internal_callback_hosts = ("127.0.0.1",)

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            # Genuine signature validation at the receiver; no key in logs.
            import time
            from types import SimpleNamespace

            from crossborder_compliance.interfaces.api.routes.workflow import sessions

            body = self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 65536))
            accepted = False
            try:
                with sessions(SimpleNamespace(app=app))() as s:
                    delivery = s.get(
                        WebhookDeliveryEntity, str(UUID(self.headers["X-Delivery-ID"]))
                    )
                    sub = s.get(WebhookSubscriptionEntity, delivery.subscription_id)
                    ctx = RepositoryContext.user(UUID(sub.tenant_id), "local-callback-verifier")
                    secret = app.state.integration_secret_store_factory(ctx).resolve(sub.secret_ref)
                    accepted = verify_signature(
                        secret,
                        self.headers["X-Delivery-ID"],
                        self.headers["X-Webhook-Timestamp"],
                        body,
                        self.headers["X-Webhook-Signature"],
                        now=time.time(),
                    )
            except Exception:
                pass
            self.send_response(200 if accepted else 401)
            self.end_headers()

        def log_message(self, *args):
            pass

    receiver = ThreadingHTTPServer(("127.0.0.1", 9110), Receiver)
    threading.Thread(target=receiver.serve_forever, daemon=True).start()
    return app


if __name__ == "__main__":
    if os.environ.get("M2E_LOCAL_UAT") != "1":
        raise SystemExit("Explicit loopback-only M2E_LOCAL_UAT=1 required")
    baseline.seed = seed
    baseline.create_host = create_host
    baseline.main()

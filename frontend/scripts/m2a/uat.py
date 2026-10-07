"""Real PG M2-A fixtures; reuse the existing loopback host and canonical H5."""
# ruff: noqa: E402 -- direct runner sets canonical repository/test import roots

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from test_m2a_intake import setup
from test_m2a_structured_intake import binding
from test_phase1f_postgres import fixture
from test_phase1i_postgres import foundation_i
from test_phase1l_b_postgres import foundation_j

from frontend.scripts.m1.uat import seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    if os.environ.get("M0_LOCAL_UAT") != "1":
        raise SystemExit("Explicit M0_LOCAL_UAT=1 required")
    if args.seed:
        if args.manifest.exists():
            raise SystemExit("Use a fresh manifest; no reset")
        people = {
            "A": seed("A"),
            "B": seed("B", partial=True),
            "C": seed("C", review=True),
            "D": seed("D", conflict=True),
        }
        f = foundation_i.__wrapped__(
            fixture.__wrapped__(), SimpleNamespace(param={"no_data": True})
        )
        f = foundation_j.__wrapped__(f, SimpleNamespace(param={}))
        binding(f)
        if os.environ.get("M2B_LOCAL_UAT") == "1":
            binding(f, code="GENERIC_FIELD", field="business_purpose", value_type="string")
        _, _, ctx, values = setup(f)
        if os.environ.get("M2B_LOCAL_UAT") == "1":
            from crossborder_compliance.domain.security import RepositoryContext
            ctx = RepositoryContext.user(ctx.tenant_id, "author", ctx.permission.scopes | {"document:read", "document:upload", "document:parse", "document:unlink"})
        people["INTAKE"] = dict(
            tenant_id=f["tenant"],
            actor_id="author",
            display_name="M2A Intake User",
            tenant_label="Synthetic intake tenant",
            permissions=sorted(ctx.permission.scopes),
            contexts=[],
            intake=values,
        )
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(people, indent=2) + "\n")
        print("Seeded real PG M1 regressions and authorized M2A session with zero preset contexts")
        return
    import uvicorn

    from crossborder_compliance.interfaces.api.main import country_compliance_router
    from crossborder_compliance.interfaces.api.routes.intake import router as intake_router
    from crossborder_compliance.interfaces.api.routes.workflow import router
    from scripts.m0_preview.server import create_demo_app

    app = create_demo_app(args.manifest)
    app.include_router(country_compliance_router)
    app.include_router(router)
    app.include_router(intake_router)
    from crossborder_compliance.interfaces.api.routes.intake_documents import router as document_router
    app.include_router(document_router)
    if os.environ.get("M2B_LOCAL_UAT") == "1":
        from crossborder_compliance.application.document_upload import DocumentFilePolicy
        from crossborder_compliance.infrastructure.document_storage import FileObjectStorageAdapter
        app.state.document_file_policy = DocumentFilePolicy.model_validate(json.loads(Path(os.environ["M2B_FILE_POLICY"]).read_text()))
        app.state.document_object_storage = FileObjectStorageAdapter(os.environ["M2B_BINARY_ROOT"])
    people = json.loads(args.manifest.read_text())

    def prepared_host(context, project, snapshot):
        for persona in people.values():
            prepared = persona.get("workflow")
            if prepared and (
                prepared["plan"]["tenant_id"],
                prepared["plan"]["project_id"],
                prepared["plan"]["analysis_snapshot_id"],
            ) == (str(context.tenant_id), str(project), str(snapshot)):
                return prepared["run"], prepared["plan"]
        raise LookupError("workflow not found")

    app.state.formal_workflow_host = prepared_host
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()

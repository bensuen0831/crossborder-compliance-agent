"""Loopback-only review UAT; reuse canonical M2-A host, parser and session."""

# ruff: noqa: E402 -- direct runner prepares canonical test import roots
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

from crossborder_compliance.infrastructure.intake_composition import prepare_snapshot
from frontend.scripts.m2a.uat import create_host
from frontend.scripts.m2a.uat import main as intake_main


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    if os.environ.get("M0_LOCAL_UAT") != "1" or os.environ.get("M2D_LOCAL_UAT") != "1":
        raise SystemExit("Explicit loopback-only M0_LOCAL_UAT=1 and M2D_LOCAL_UAT=1 required")
    if args.seed:
        saved = sys.argv[:]
        sys.argv = ["uat.py", "--manifest", str(args.manifest), "--seed"]
        intake_main()
        sys.argv = saved
        people = json.loads(args.manifest.read_text())
        f = foundation_i.__wrapped__(
            fixture.__wrapped__(), SimpleNamespace(param={"no_data": True})
        )
        f = foundation_j.__wrapped__(f, SimpleNamespace(param={}))
        binding(f)
        binding(f, code="GENERIC_FIELD", field="business_purpose", value_type="string")
        _, _, ctx, values = setup(f)
        permissions = set(ctx.permission.scopes) | {
            "workflow:review",
            "document:read",
            "document:upload",
            "document:parse",
            "document:unlink",
        }
        people["REVIEW"] = dict(
            tenant_id=f["tenant"],
            actor_id="author",
            display_name="M2D Reviewer",
            tenant_label="Synthetic review tenant",
            permissions=sorted(permissions),
            contexts=[],
            intake=values,
        )
        people["REVIEW_READER"] = {
            **people["REVIEW"],
            "display_name": "M2D read-only reviewer",
            "permissions": sorted(permissions - {"workflow:review"}),
        }
        args.manifest.write_text(json.dumps(people, indent=2) + "\n")
        print("M2D governed fixture seeded")
        return
    app = create_host(args.manifest)
    from crossborder_compliance.interfaces.api.routes.reviews import router

    app.include_router(router)
    people = json.loads(args.manifest.read_text())
    review_tenant = people["REVIEW"]["tenant_id"]

    def prepared(sessions, context, intake, snapshot_id, run_id):
        return prepare_snapshot(
            sessions,
            context,
            intake,
            snapshot_id,
            run_id,
            requirement_confirmation=str(context.tenant_id) == review_tenant,
        )

    app.state.intake_snapshot_preparer = prepared
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()

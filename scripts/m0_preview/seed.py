"""Local UAT only: reuse reviewed Phase 1F/G fixtures against real PostgreSQL.

This adds synthetic data, never modifies an existing analysis or resets a DB.
It is not a production ingestion, identity, registry or publication mechanism.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

from phase1g_fixtures import publish  # noqa: E402
from test_phase1f_postgres import binding, fixture, scope  # noqa: E402
from test_phase1g_persistence_postgres import policies  # noqa: E402

from crossborder_compliance.domain.retrieval import KnowledgeRetrievalQuery  # noqa: E402


def seed_persona(label):
    f = fixture.__wrapped__()
    visible = publish(f, [binding(f, permissions=["read:internal"])])
    hidden = publish(f, [binding(f, permissions=["secret:read"])])
    r, policy, _ = policies(f)
    # Freeze each allowed universe after publication, through the existing resolver.
    scope(f, snapshot_id=f["snapshot"])
    return {
        "tenant_id": f["tenant"],
        "actor_id": f["ctx"].user_context.user_id,
        "display_name": f"UAT User {label}",
        "tenant_label": f"Synthetic Tenant {label}",
        "permissions": sorted(f["ctx"].permission.scopes),
        "contexts": [{
            "project_id": f["project"],
            "display_name": f"Generic Project · UAT {label}",
            "analysis_snapshot_id": f["snapshot"],
            "policy_id": policy["policy_id"],
        }],
        "visible_version": visible["knowledge_version_id"],
        "forbidden_version": hidden["knowledge_version_id"],
        "query_schema": KnowledgeRetrievalQuery.__name__,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Manifest exists; reuse it or choose a new file. No data was reset.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"A": seed_persona("A"), "B": seed_persona("B")}, indent=2) + "\n")
    print("Seeded two isolated synthetic tenants and permission-restricted versions.")


if __name__ == "__main__":
    main()

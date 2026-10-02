from __future__ import annotations

import argparse
import json
from pathlib import Path
from sqlalchemy import inspect
from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_engine
from crossborder_compliance.infrastructure.persistence.models import Base
from smoke.evidence_utils import EVIDENCE_DIR, write_json, write_markdown

STATE_JSON = EVIDENCE_DIR / "postgres_schema_state.json"
CHECKPOINT_PREFIXES = ("checkpoint",)

def _snapshot() -> dict[str, object]:
    import psycopg
    settings = get_settings()
    engine = build_engine(settings.database_url)
    domain_tables = sorted(inspect(engine).get_table_names())
    with psycopg.connect(settings.langgraph_database_uri) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() ORDER BY table_name")
            all_tables = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT version_num FROM alembic_version")
            alembic_revision = cur.fetchone()[0]
            cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
            row = cur.fetchone()
            vector_version = row[0] if row else None
    checkpoint_tables = sorted(t for t in all_tables if t.startswith(CHECKPOINT_PREFIXES))
    return {
        "alembic_revision": alembic_revision,
        "pgvector_installed_version": vector_version,
        "all_tables": all_tables,
        "domain_tables_from_database": domain_tables,
        "domain_tables_from_sqlalchemy_metadata": sorted(Base.metadata.tables.keys()),
        "checkpoint_tables": checkpoint_tables,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=["post-alembic", "post-runtime"])
    args = parser.parse_args()
    current = _snapshot()
    state = json.loads(STATE_JSON.read_text()) if STATE_JSON.exists() else {}
    state[args.phase] = current
    write_json("postgres_schema_state.json", state)

    if args.phase == "post-alembic":
        ok = (
            current["alembic_revision"] in {"0002_phase1b", "0003_phase1c", "0004_phase1d", "0005_phase1e", "0006_phase1f", "0007_phase1g", "0008_phase1h"}
            and bool(current["pgvector_installed_version"])
            and not current["checkpoint_tables"]
            and "checkpoints" not in current["domain_tables_from_sqlalchemy_metadata"]
        )
        print(json.dumps({"post_alembic_schema_proof": ok, **current}, indent=2, sort_keys=True))
        raise SystemExit(0 if ok else 2)

    before = state.get("post-alembic", {})
    after = state["post-runtime"]
    runtime_created_checkpoint_schema = (
        not before.get("checkpoint_tables")
        and "checkpoints" in after.get("checkpoint_tables", [])
        and "checkpoints" not in after.get("domain_tables_from_sqlalchemy_metadata", [])
    )
    evidence = {
        "domain_alembic_created_domain_schema": before.get("alembic_revision") in {"0002_phase1b", "0003_phase1c", "0004_phase1d", "0005_phase1e", "0006_phase1f", "0007_phase1g", "0008_phase1h"},
        "pgvector_extension_available_and_installed": bool(after.get("pgvector_installed_version")),
        "checkpoint_tables_absent_immediately_after_domain_alembic": not bool(before.get("checkpoint_tables")),
        "langgraph_setup_created_checkpoint_schema": runtime_created_checkpoint_schema,
        "domain_metadata_excludes_checkpoint_tables": "checkpoints" not in after.get("domain_tables_from_sqlalchemy_metadata", []),
        "post_alembic": before,
        "post_runtime": after,
    }
    sections = [
        ("Decision", "**PASS**" if all(evidence[k] for k in [
            "domain_alembic_created_domain_schema",
            "pgvector_extension_available_and_installed",
            "checkpoint_tables_absent_immediately_after_domain_alembic",
            "langgraph_setup_created_checkpoint_schema",
            "domain_metadata_excludes_checkpoint_tables",
        ]) else "**FAIL**"),
        ("Assertions", "\n".join(f"- {k}: **{'PASS' if v else 'FAIL'}**" for k, v in evidence.items() if isinstance(v, bool))),
        ("Post-Alembic Snapshot", f"```json\n{json.dumps(before, indent=2, sort_keys=True)}\n```"),
        ("Post-Runtime Snapshot", f"```json\n{json.dumps(after, indent=2, sort_keys=True)}\n```"),
    ]
    write_markdown("postgres_schema_evidence.md", "Phase 1B PostgreSQL Schema + Phase 1A Checkpointer Separation Evidence", sections)
    ok = all(v for k, v in evidence.items() if isinstance(v, bool))
    print(json.dumps(evidence, indent=2, sort_keys=True))
    raise SystemExit(0 if ok else 2)

if __name__ == "__main__":
    main()

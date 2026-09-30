from __future__ import annotations
import importlib.metadata
import platform
from crossborder_compliance.config import get_settings
from smoke.evidence_utils import write_markdown

def _version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "MISSING"

def main() -> None:
    import psycopg
    import redis
    settings = get_settings()
    with psycopg.connect(settings.langgraph_database_uri) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            postgres_version = cur.fetchone()[0]
            cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
            row = cur.fetchone()
            pgvector_version = row[0] if row else "NOT_INSTALLED"
    r = redis.Redis.from_url(settings.redis_url)
    redis_info = r.info(section="server")
    versions = {
        "Python": platform.python_version(),
        "PostgreSQL": str(postgres_version),
        "pgvector": str(pgvector_version),
        "Redis": str(redis_info.get("redis_version", "UNKNOWN")),
        "langgraph": _version("langgraph"),
        "langgraph-checkpoint-postgres": _version("langgraph-checkpoint-postgres"),
        "psycopg": _version("psycopg"),
    }
    table = "\n".join(["| Component | Version |", "|---|---|"] + [f"| {k} | `{v}` |" for k, v in versions.items()])
    write_markdown("runtime_versions.md", "Phase 1A.1 Runtime Versions", [("Environment", table)])
    for k, v in versions.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import platform
import socket
from urllib.parse import urlparse
from crossborder_compliance.config import get_settings

REQUIRED_MODULES = ("langgraph", "psycopg", "redis")
REQUIRED_DISTS = ("langgraph", "langgraph-checkpoint-postgres", "psycopg", "redis")

def _dist_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for dist in REQUIRED_DISTS:
        try:
            versions[dist] = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            versions[dist] = "MISSING"
    return versions

def main() -> None:
    settings = get_settings()
    checks: dict[str, object] = {
        "python_version": platform.python_version(),
        "python_modules": {m: importlib.util.find_spec(m) is not None for m in REQUIRED_MODULES},
        "package_versions": _dist_versions(),
    }
    parsed = urlparse(settings.langgraph_database_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    try:
        with socket.create_connection((host, port), timeout=3):
            pass
        checks["postgres_tcp"] = True
    except OSError as exc:
        checks["postgres_tcp"] = False
        checks["postgres_tcp_error"] = str(exc)

    checks["postgres_login"] = False
    checks["pgvector_available"] = False
    if checks["python_modules"].get("psycopg") and checks["postgres_tcp"]:
        try:
            import psycopg
            with psycopg.connect(settings.langgraph_database_uri) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version()")
                    checks["postgres_version"] = cur.fetchone()[0]
                    cur.execute("SELECT default_version, installed_version FROM pg_available_extensions WHERE name = 'vector'")
                    row = cur.fetchone()
                    checks["pgvector_available"] = row is not None
                    checks["pgvector_default_version"] = row[0] if row else None
                    checks["pgvector_installed_version_before_migration"] = row[1] if row else None
            checks["postgres_login"] = True
        except Exception as exc:
            checks["postgres_error"] = f"{type(exc).__name__}: {exc}"

    checks["redis_ping"] = False
    if checks["python_modules"].get("redis"):
        try:
            import redis
            client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3)
            checks["redis_ping"] = bool(client.ping())
            info = client.info(section="server")
            checks["redis_version"] = info.get("redis_version")
        except Exception as exc:
            checks["redis_error"] = f"{type(exc).__name__}: {exc}"

    modules_ok = all(bool(v) for v in checks["python_modules"].values())
    versions_ok = all(v != "MISSING" for v in checks["package_versions"].values())
    ready = all([modules_ok, versions_ok, bool(checks["postgres_tcp"]), bool(checks["postgres_login"]),
                 bool(checks["pgvector_available"]), bool(checks["redis_ping"])])
    checks["ready_for_mandatory_smoke"] = ready
    print(json.dumps(checks, indent=2, sort_keys=True))
    raise SystemExit(0 if ready else 2)

if __name__ == "__main__":
    main()

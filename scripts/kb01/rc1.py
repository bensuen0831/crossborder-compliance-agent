"""KB01-Technical-UAT-RC1 lifecycle for isolated Linux/amd64 local testing.

Uses the existing UAT host, React app, canonical workers and ci_services S3.
This is not a production identity adapter or a remotely exposed staging server.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
VERSION = "KB01-Technical-UAT-RC1"


def private(path, value):
    with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as output:
        json.dump(value, output, indent=2)


def docker(*args, check=True):
    env = os.environ.copy()
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        env.pop(key, None)
    return subprocess.run(
        ["docker", "--host=unix:///var/run/docker.sock", *args],
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def settings(root):
    path = root / "private.json"
    if not path.exists():
        private(
            path,
            {
                "instance": "kb01-rc1-" + secrets.token_hex(6),
                "postgres_password": secrets.token_urlsafe(32),
            },
        )
    path.chmod(0o600)
    return json.loads(path.read_text())


def environment(root, config):
    password = quote(config["postgres_password"], safe="")
    env = {
        **os.environ,
        "APP_ENV": "LOCAL_SERVER",
        "M0_LOCAL_UAT": "1",
        "KB01_LOCAL_UAT": "1",
        "DATABASE_URL": f"postgresql+psycopg://kb01:{password}@127.0.0.1:65432/kb01_rc1",
        "LANGGRAPH_DATABASE_URI": f"postgresql://kb01:{password}@127.0.0.1:65432/kb01_rc1?sslmode=disable",
        "REDIS_URL": "redis://127.0.0.1:16379/0",
        "LANGGRAPH_STRICT_MSGPACK": "true",
        "PYTHONPATH": str(ROOT / "src") + os.pathsep + str(ROOT),
        "VITE_M0_DEMO": "true",
        "VITE_KB01_UAT": "true",
        "VITE_SESSION_PATH": "/m0-demo/session",
        "M0_API_TARGET": "http://127.0.0.1:18010",
        "M0_FRONTEND_URL": "http://127.0.0.1:15173",
    }
    for key in ("DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        env.pop(key, None)
    env["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    env.setdefault("BUILDX_CONFIG", str(root / "buildx"))
    service = root / "services/service-evidence.json"
    if service.exists():
        env.update(json.loads(service.read_text())["variables"])
        env["KB01_TEST_SCAN_DATABASE"] = str(root / "services/scan/official-signatures")
        env["KB01_TEST_SCAN_IDENTITY"] = "OFFICIAL_CLAMAV_VERIFIED_CVD_MAIN_DAILY_BYTECODE"
    return env


def run(root, env, name, command):
    with (root / (name + ".log")).open("a") as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError("RC1_STEP_FAILED:" + name + "; use logs --service " + name)


def spawn(root, env, name, command):
    with (root / (name + ".log")).open("a") as log:
        process = subprocess.Popen(
            command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
    # Start-time identity prevents killing a later unrelated process after PID reuse.
    marker = Path("/proc") / str(process.pid) / "stat"
    fields = marker.read_text().rsplit(")", 1)[1].split()
    (root / (name + ".pid.json")).write_text(
        json.dumps({"pid": process.pid, "start_ticks": fields[19]})
    )


def stop_process(root, name):
    path = root / (name + ".pid.json")
    if not path.exists():
        return
    saved = json.loads(path.read_text())
    marker = Path("/proc") / str(saved["pid"]) / "stat"
    if marker.exists() and marker.read_text().rsplit(")", 1)[1].split()[19] == saved["start_ticks"]:
        os.killpg(saved["pid"], signal.SIGTERM)
        for _ in range(50):
            if not marker.exists():
                break
            time.sleep(0.1)
    path.unlink(missing_ok=True)


def owned_container(config, name):
    result = docker("container", "inspect", name, check=False)
    if result.returncode:
        return None
    info = json.loads(result.stdout)[0]
    if info["Config"]["Labels"].get("kb01.rc1.instance") != config["instance"]:
        raise RuntimeError("RC1_CONTAINER_OWNER_MISMATCH")
    return info


def containers(root, config):
    locks = json.loads((ROOT / "scripts/kb01/rc1_services.lock.json").read_text())
    for service, port, target in [("postgres", 65432, 5432), ("redis", 16379, 6379)]:
        name = config["instance"] + "-" + service
        current = owned_container(config, name)
        if current:
            if not current["State"]["Running"]:
                docker("start", name)
            continue
        volume = name + "-data"
        docker("volume", "create", "--label", "kb01.rc1.instance=" + config["instance"], volume)
        command = [
            "run",
            "--detach",
            "--name",
            name,
            "--label",
            "kb01.rc1.instance=" + config["instance"],
            "--publish",
            f"127.0.0.1:{port}:{target}",
            "--mount",
            f"type=volume,src={volume},dst="
            + ("/var/lib/postgresql/data" if service == "postgres" else "/data"),
        ]
        if service == "postgres":
            credentials = root / "postgres.env"
            if not credentials.exists():
                with open(credentials, "x", opener=lambda n, f: os.open(n, f, 0o600)) as output:
                    output.write(
                        "POSTGRES_USER=kb01\nPOSTGRES_DB=kb01_rc1\nPOSTGRES_PASSWORD="
                        + config["postgres_password"]
                        + "\n"
                    )
            command += ["--env-file", str(credentials)]
        command += [locks[service]["image"]]
        if service == "redis":
            command += ["redis-server", "--appendonly", "yes"]
        docker(*command)


def health():
    rows = {}
    for name, url in [
        ("backend", "http://127.0.0.1:18010/health/live"),
        ("frontend", "http://127.0.0.1:15173"),
    ]:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                rows[name] = {"url": url, "status": response.status}
        except Exception:
            rows[name] = {"url": url, "status": "UNAVAILABLE"}
    return rows


def demo_taxonomy(root, config, count):
    """Explicit synthetic demo command through existing application governance."""
    from uuid import UUID

    from crossborder_compliance.application.knowledge_taxonomy import KnowledgeTaxonomyService
    from crossborder_compliance.domain.knowledge_management import (
        CreateTaxonomy,
        MutateTaxonomy,
        TaxonomyPayload,
    )
    from crossborder_compliance.domain.security import RepositoryContext
    from crossborder_compliance.infrastructure.persistence.db import build_session_factory
    from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
        PostgresKnowledgeTaxonomyRepository,
    )

    people = json.loads((root / "personas.json").read_text())
    sf = build_session_factory(environment(root, config)["DATABASE_URL"])[1]

    def owner(name):
        p = people[name]
        ctx = RepositoryContext.user(UUID(p["tenant_id"]), p["actor_id"], set(p["permissions"]))
        return KnowledgeTaxonomyService(PostgresKnowledgeTaxonomyRepository(sf, ctx), ctx)

    for n in range(count):
        code = f"RC1-SYNTHETIC-CATEGORY-{n + 1:03}"
        marker = root / (code + ".json")
        if marker.exists():
            continue
        made = owner("A").mutate(
            "CREATE",
            None,
            CreateTaxonomy(
                kind="REGULATION_CATEGORY",
                code=code,
                display_name="SYNTHETIC_GOVERNED_TEST_DATA " + str(n + 1),
                payload=TaxonomyPayload(),
                idempotency_key=code + "-create",
            ),
        )
        current = made
        for action, actor in [
            ("SUBMIT_REVIEW", "A"),
            ("APPROVE", "REVIEWER"),
            ("PUBLISH", "PUBLISHER"),
        ]:
            current = owner(actor).mutate(
                action,
                UUID(made["version_id"]),
                MutateTaxonomy(
                    expected_record_version=current["record_version"],
                    idempotency_key=code + "-" + action,
                    reason="Explicit isolated RC1 synthetic demo initialization",
                ),
            )
        marker.write_text(
            json.dumps(
                {
                    "definition_id": made["definition_id"],
                    "version_id": made["version_id"],
                    "label": "SYNTHETIC_GOVERNED_TEST_DATA",
                }
            )
        )
    sf.kw["bind"].dispose()


def wait_http():
    for _ in range(90):
        if all(x["status"] == 200 for x in health().values()):
            return
        time.sleep(1)
    raise RuntimeError("RC1_HTTP_NOT_READY")


def validate_tool_sources(proof):
    """Cached evidence must bind the current build recipe and inventory reader."""
    for key, relative in (
        ("containerfile_sha256", "scripts/kb01/Containerfile"),
        ("inventory_script_sha256", "scripts/kb01/image_inventory.py"),
    ):
        expected = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if proof.get(key) != expected:
            raise RuntimeError("RC1_TOOL_SOURCE_MISMATCH")


def start(root, config, args):
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
        raise RuntimeError("RC1_SUPPORTED_PLATFORM_LINUX_AMD64_REQUIRED")
    if any(x["status"] == 200 for x in health().values()):
        raise RuntimeError("RC1_PORTS_ALREADY_IN_USE; status first, then stop only owned RC1")
    docker("info", "--format", "{{.ServerVersion}}")
    containers(root, config)
    env = environment(root, config)
    import psycopg
    from redis import Redis

    for attempt in range(90):
        try:
            with psycopg.connect(env["LANGGRAPH_DATABASE_URI"]):
                pass
            assert Redis.from_url(env["REDIS_URL"]).ping()
            break
        except Exception:
            if attempt == 89:
                raise RuntimeError("RC1_DATABASE_OR_REDIS_NOT_READY") from None
            time.sleep(1)
    tool = root / "tool-image.json"
    if args.tool_evidence:
        supplied = json.loads(args.tool_evidence.read_text())
        validate_tool_sources(supplied)
        # External provenance paths are local state, never a release claim.
        tool.write_text(json.dumps(supplied))
    elif not tool.exists():
        run(
            root,
            env,
            "tools",
            [
                sys.executable,
                "scripts/kb01/build_tools.py",
                "--output",
                str(tool),
                "--tag",
                "kb01-rc1-tools:local",
            ],
        )
    proof = json.loads(tool.read_text())
    validate_tool_sources(proof)
    if not proof.get("oci_manifest_digest") or not proof.get("provenance_path"):
        raise RuntimeError("RC1_TOOL_PROVENANCE_INCOMPLETE")
    provenance = json.loads(Path(proof["provenance_path"]).read_text())
    if (
        provenance["oci"]["config_digest"] != proof["image_id"]
        or provenance["oci"]["manifest_digest"] != proof["oci_manifest_digest"]
    ):
        raise RuntimeError("RC1_TOOL_PROVENANCE_IDENTITY_MISMATCH")
    for relative, expected in proof["source_sha256"].items():
        if (
            hashlib.sha256(
                (ROOT / "src/crossborder_compliance" / relative).read_bytes()
            ).hexdigest()
            != expected
        ):
            raise RuntimeError("RC1_TOOL_PARSER_SOURCE_CHANGED")
    run(root, env, "migration", [sys.executable, "-m", "alembic", "upgrade", "head"])
    services = root / "services"
    cmd = [
        sys.executable,
        "scripts/kb01/ci_services.py",
        "--root",
        str(services),
        "--tool-evidence",
        str(tool),
        "--port-offset",
        "100",
    ]
    if services.exists():
        cmd.append("--resume")
    run(root, env, "services", cmd)
    env = environment(root, config)
    signatures = root / "services/scan/official-signatures"
    image = json.loads(tool.read_text())["image_id"]
    run(
        root,
        env,
        "signatures",
        [
            sys.executable,
            "scripts/kb01/official_signatures.py",
            "--root",
            str(signatures),
            "--image",
            image,
            "--evidence",
            str(root / "official-signatures.json"),
        ],
    )
    manifest = root / "personas.json"
    if not manifest.exists():
        run(
            root,
            env,
            "seed",
            [sys.executable, "scripts/kb01/uat.py", "--manifest", str(manifest), "--seed"],
        )
    if not (ROOT / "frontend/node_modules/.bin/vite").exists():
        run(root, env, "npm", ["npm", "ci", "--prefix", "frontend"])
    spawn(
        root,
        env,
        "backend",
        [sys.executable, "scripts/kb01/uat.py", "--manifest", str(manifest), "--port", "18010"],
    )
    spawn(
        root,
        env,
        "frontend",
        ["npm", "--prefix", "frontend", "run", "dev", "--", "--port", "15173"],
    )
    wait_http()
    status(root, config)


def stop(root, config):
    for name in ("frontend", "backend"):
        stop_process(root, name)
    saved = root / "services/process.json"
    if saved.exists():
        info = json.loads(saved.read_text())
        proc = Path("/proc") / str(info["pid"])
        # S3 executable and retained data root are exact task-owned selectors.
        try:
            if (proc / "exe").resolve() == Path(info["executable"]).resolve():
                os.killpg(info["pid"], signal.SIGTERM)
        except (ProcessLookupError, FileNotFoundError):
            pass
    for service in ("postgres", "redis"):
        name = config["instance"] + "-" + service
        if owned_container(config, name):
            docker("stop", "--time", "10", name)
    print("RC1 stopped; PostgreSQL volumes and versioned S3 originals retained.")


def status(root, config):
    result = {
        "version": VERSION,
        "scope": "LOCAL_ISOLATED_TECHNICAL_TESTING_ONLY",
        "http": health(),
        "instance": config["instance"],
        "state_directory": str(root),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "stage2": "NOT STARTED",
        "production_auth": "NOT PROVIDED",
    }
    for service in ("postgres", "redis"):
        item = owned_container(config, config["instance"] + "-" + service)
        result[service] = "RUNNING" if item and item["State"]["Running"] else "STOPPED"
    proof = root / "tool-image.json"
    if proof.exists():
        value = json.loads(proof.read_text())
        result["image_id"] = value["image_id"]
        result["oci_manifest_digest"] = value.get("oci_manifest_digest")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["start", "stop", "status", "health", "demo", "logs", "diagnose", "reset"],
    )
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".local/share/kb01-rc1")
    parser.add_argument("--tool-evidence", type=Path)
    parser.add_argument(
        "--service",
        default="backend",
        choices=[
            "backend",
            "frontend",
            "tools",
            "services",
            "migration",
            "seed",
            "npm",
            "signatures",
        ],
    )
    parser.add_argument("--confirm-reset", default="")
    parser.add_argument("--taxonomy-rows", type=int, default=4, choices=range(1, 101))
    args = parser.parse_args()
    root = args.state_dir.resolve()
    if root in (Path("/"), Path.home(), ROOT) or root in ROOT.parents or ROOT in root.parents:
        raise SystemExit("DEDICATED_RC1_STATE_DIRECTORY_REQUIRED")
    if root.exists() and not (root / "private.json").exists() and any(root.iterdir()):
        raise SystemExit("EMPTY_OR_EXISTING_RC1_STATE_DIRECTORY_REQUIRED")
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    config = settings(root)
    try:
        if args.command == "start":
            start(root, config, args)
        elif args.command == "stop":
            stop(root, config)
        elif args.command in ("status", "health", "diagnose"):
            status(root, config)
        elif args.command == "demo":
            env = environment(root, config)
            run(
                root,
                env,
                "fixtures",
                [
                    sys.executable,
                    "scripts/kb01/generate_fixtures.py",
                    "--output",
                    str(root / "demo-originals"),
                ],
            )
            print(
                "Genuine SYNTHETIC test originals: "
                + str(root / "demo-originals/originals.json")
                + "; use UI Upload, Review, Publish."
            )
            demo_taxonomy(root, config, args.taxonomy_rows)
            print(
                "Published synthetic categories through distinct author/reviewer/publisher owners."
            )
        elif args.command == "logs":
            path = root / (args.service + ".log")
            text = (
                "\n".join(path.read_text(errors="replace").splitlines()[-80:])
                if path.exists()
                else "No log yet"
            )
            text = re.sub(r"(https?://[^\s?]+)\?[^\s]*", r"\1?[REDACTED]", text)
            text = re.sub(r"(postgresql[^:]*://)[^@\s]+@", r"\1[REDACTED]@", text)
            print(text)
        elif args.command == "reset":
            if args.confirm_reset != config["instance"]:
                raise RuntimeError("RESET_REQUIRES_EXACT_INSTANCE_FROM_STATUS")
            stop(root, config)
            for service in ("postgres", "redis"):
                name = config["instance"] + "-" + service
                if owned_container(config, name):
                    docker("rm", name)
                # Exact owned volumes only; an unrelated global volume is untouched.
                item = docker("volume", "inspect", name + "-data", check=False)
                if (
                    item.returncode == 0
                    and json.loads(item.stdout)[0].get("Labels", {}).get("kb01.rc1.instance")
                    == config["instance"]
                ):
                    docker("volume", "rm", name + "-data")
            archived = root.with_name(
                root.name + ".retained-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            )
            root.rename(archived)
            print(
                "Reset completed; local files retained privately at "
                + str(archived)
                + "; start creates a new isolated instance."
            )
    except Exception as error:
        # CLI errors are stable names, never repr(config/credentials/provider data).
        print(
            "RC1_OPERATION_FAILED: "
            + type(error).__name__
            + "; "
            + (str(error) if isinstance(error, RuntimeError) else "check private local logs"),
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

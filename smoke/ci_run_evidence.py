from __future__ import annotations
import os
import json
import subprocess
from pathlib import Path
from smoke.evidence_utils import write_markdown

def main() -> None:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    event = json.loads(Path(event_path).read_text()) if event_path else {}
    pr_head = event.get("pull_request", {}).get("head", {}).get("sha")
    checkout_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    run_id = os.getenv("GITHUB_RUN_ID", "LOCAL_OR_UNKNOWN")
    server = os.getenv("GITHUB_SERVER_URL", "")
    repo = os.getenv("GITHUB_REPOSITORY", "")
    url = f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id != "LOCAL_OR_UNKNOWN" else "N/A"
    fields = {
        "run_id": run_id,
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", "N/A"),
        "repository": repo or "N/A",
        "workflow": os.getenv("GITHUB_WORKFLOW", "N/A"),
        "job": os.getenv("GITHUB_JOB", "N/A"),
        "sha": os.getenv("GITHUB_SHA", "N/A"),
        "tested_pr_head_sha": pr_head or checkout_sha,
        "runner_checkout_sha": checkout_sha,
        "ref": os.getenv("GITHUB_REF", "N/A"),
        "runner_os": os.getenv("RUNNER_OS", "N/A"),
        "run_url": url,
    }
    body = "\n".join(f"- **{k}**: `{v}`" for k, v in fields.items())
    write_markdown("ci_run_evidence.md", "Phase 1A.1 CI Run Evidence", [("Run Identifier", body)])
    evidence_dir = Path(os.getenv("EVIDENCE_DIR", "artifacts/phase1a-runtime"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "ci_run_evidence.json").write_text(json.dumps(fields, indent=2)+"\n")
    print(body)

if __name__ == "__main__":
    main()

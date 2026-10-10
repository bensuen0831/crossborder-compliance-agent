"""Northbound HTTP client: transport, authentication and bounded polling only."""

import json
import time
from typing import Any, BinaryIO, TypedDict
from urllib.parse import quote

import httpx

from .contracts import IntakeUpdate, ProjectCreate, validate

JSON = dict[str, Any]


class AnalysisAccepted(TypedDict):
    project_id: str
    analysis_snapshot_id: str
    workflow_run_id: str
    status: str
    status_url: str
    result_url: str
    events_url: str


class GatewayError(Exception):
    def __init__(self, status, code, trace_id=None, retryable=False):
        self.status, self.code, self.trace_id, self.retryable = status, code, trace_id, retryable
        super().__init__(code)


class AgentClient:
    def __init__(self, base_url: str, *, timeout=60, client: httpx.Client | None = None):
        self._http = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)
        self._owned = client is None
        self._bearer: str | None = None

    def close(self):
        if self._owned:
            self._http.close()

    def use_service_credential(self, credential: str):
        self._bearer = credential

    def _call(self, method: str, path: str, *, key=None, **kwargs) -> JSON:
        headers = {"Accept": "application/json"}
        if self._bearer:
            headers["Authorization"] = "Bearer " + self._bearer
        if key:
            headers["Idempotency-Key"] = key
        response = self._http.request(method, "/api/v1/external" + path, headers=headers, **kwargs)
        if response.is_error:
            try:
                value = response.json()
            except ValueError:
                value = {}
            raise GatewayError(
                response.status_code,
                value.get("error_code", "GATEWAY_UNAVAILABLE"),
                value.get("trace_id"),
                value.get("retryable", False),
            )
        return response.json()

    def authenticate(self, client_id: str, client_secret: str, scope: str | None = None) -> JSON:
        value = self._call(
            "POST",
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                **({"scope": scope} if scope else {}),
            },
        )
        self._bearer = value["access_token"]
        return value

    def create_project(self, input: ProjectCreate, key: str) -> JSON:
        validate("ExternalProjectCreate", input)
        return self._call("POST", "/projects", json=input, key=key)

    def get_intake(self, project: str) -> JSON:
        return self._call("GET", f"/projects/{quote(project, safe='')}/intake")

    def update_intake(self, project: str, input: IntakeUpdate, key: str) -> JSON:
        validate("ExternalIntakeUpdate", input)
        return self._call("PUT", f"/projects/{quote(project, safe='')}/intake", json=input, key=key)

    def upload_document(
        self,
        project: str,
        file: BinaryIO,
        filename: str,
        media_type: str,
        expected_version: int,
        key: str,
    ) -> JSON:
        return self._call(
            "POST",
            f"/projects/{quote(project, safe='')}/documents",
            key=key,
            data={"expected_version": expected_version},
            files={"file": (filename, file, media_type)},
        )

    def parse_document(self, project: str, version: str, expected_version: int, key: str) -> JSON:
        return self._call(
            "POST",
            f"/projects/{quote(project, safe='')}/documents/{quote(version, safe='')}/parse",
            key=key,
            json={"expected_version": expected_version},
        )

    def list_eligible_models(self, project: str) -> JSON:
        return self._call("GET", f"/projects/{quote(project, safe='')}/eligible-models")

    def confirm(self, project: str, expected_version: int, key: str) -> JSON:
        return self._call(
            "POST",
            f"/projects/{quote(project, safe='')}/intake/confirm",
            key=key,
            json={"expected_version": expected_version},
        )

    def start_analysis(self, project: str, snapshot: str, key: str) -> AnalysisAccepted:
        return self._call(
            "POST",
            f"/projects/{quote(project, safe='')}/snapshots/{quote(snapshot, safe='')}/workflow",
            key=key,
            json={},
        )

    def get_status(self, run: str) -> JSON:
        return self._call("GET", f"/workflows/{quote(run, safe='')}")

    def get_result(self, run: str) -> JSON:
        return self._call("GET", f"/workflows/{quote(run, safe='')}/stage1-result")

    def subscribe_webhook(self, input: JSON, key: str) -> JSON:
        validate("WebhookCreate", input)
        return self._call("POST", "/webhook-subscriptions", json=input, key=key)

    def wait_for_completion(self, run: str, *, timeout=60, interval=1) -> JSON:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self.get_status(run)
            if value["status"] != "RUNNING":
                return value
            time.sleep(min(interval, max(0, deadline - time.monotonic())))
        raise GatewayError(408, "POLL_TIMEOUT", retryable=True)

    def events(self, run: str, last_event_id: str | None = None):
        headers = {"Accept": "text/event-stream", "Authorization": "Bearer " + (self._bearer or "")}
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        with self._http.stream(
            "GET", f"/api/v1/external/workflows/{quote(run, safe='')}/events", headers=headers
        ) as response:
            if response.is_error:
                raise GatewayError(response.status_code, "EVENT_STREAM_DENIED")
            for line in response.iter_lines():
                if line.startswith("data: "):
                    yield validate("ExternalWorkflowEvent", json.loads(line[6:]))

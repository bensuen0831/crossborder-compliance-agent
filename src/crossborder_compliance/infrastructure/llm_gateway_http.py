"""Thin HTTP protocols, never provider selection or model/data policy."""

import ipaddress
import json
import socket
import time
from urllib.parse import urlparse

import httpx

from crossborder_compliance.domain.llm_gateway import (
    GatewayDenied,
    ModelOperation,
    ProviderFailure,
    ProviderResult,
)


def check_endpoint(url, external):
    p = urlparse(url)
    if (
        p.scheme not in ("http", "https")
        or not p.hostname
        or p.username
        or p.password
        or p.query
        or p.fragment
        or (external and p.scheme != "https")
    ):
        raise GatewayDenied("MODEL_ENDPOINT_INVALID")
    if external:
        try:
            ips = [x[4][0] for x in socket.getaddrinfo(p.hostname, p.port or 443)]
            if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
                raise GatewayDenied("MODEL_ENDPOINT_INVALID")
        except Exception:
            raise GatewayDenied("MODEL_ENDPOINT_INVALID") from None


class HTTPProviderAdapter:
    """Canonical generic REST protocol; other provider types can use the same thin adapter."""

    supported_operations = frozenset(ModelOperation)

    def __init__(
        self, connection_source, secrets, *, transport=None, endpoint_check=check_endpoint
    ):
        self.connections, self.secrets = connection_source, secrets
        self.transport, self.endpoint_check = transport, endpoint_check

    def _wire(self, model, payload, connection):
        path = connection.endpoint.get("paths", {}).get(payload.operation.value)
        body = {
            "model": connection.model_name,
            "operation": payload.operation.value,
            "inputs": list(payload.texts),
            "system_prompt": payload.system_prompt,
            "output_schema": payload.output_schema,
            "max_output_tokens": payload.max_output_tokens,
        }
        return "POST", path, body

    def _prepare(self, model, payload):
        if payload.operation not in self.supported_operations:
            raise GatewayDenied("PROVIDER_CAPABILITY_UNSUPPORTED")
        connection = self.connections.connection(model)
        method, path, body = self._wire(model, payload, connection)
        base = str(connection.endpoint.get("url", "")).rstrip("/")
        self.endpoint_check(base, connection.external)
        if (
            not isinstance(path, str)
            or not path.startswith("/")
            or path.startswith("//")
            or any(part in path for part in ("..", "?", "#", "\\"))
        ):
            raise GatewayDenied("MODEL_ENDPOINT_INVALID")
        secret = None
        headers = {"Content-Type": "application/json"}
        if connection.auth_type != "NONE":
            if connection.auth_type != "BEARER_SECRET_REF" or not connection.secret_ref:
                raise GatewayDenied("MODEL_AUTH_CONFIGURATION_INVALID")
            try:
                secret = self.secrets.resolve(connection.secret_ref)
                if not secret or "\n" in secret or "\r" in secret:
                    raise ValueError()
                headers["Authorization"] = "Bearer " + secret
            except Exception:
                raise GatewayDenied("MODEL_SECRET_UNAVAILABLE") from None
        seconds = float(connection.timeout_policy.get("seconds", 30))
        attempts = int(connection.retry_policy.get("max_attempts", 1))
        backoff = float(connection.retry_policy.get("backoff_seconds", 0))
        limit = int(connection.endpoint.get("max_response_bytes", 1048576))
        if not (
            0 < seconds <= 300
            and 1 <= attempts <= 5
            and 0 <= backoff <= 30
            and 1 <= limit <= 16777216
        ):
            raise GatewayDenied("MODEL_TRANSPORT_CONFIGURATION_INVALID")
        return (
            connection,
            method,
            base + path,
            body,
            headers,
            secret,
            seconds,
            attempts,
            backoff,
            limit,
        )

    @staticmethod
    def _without_secret(value, secret):
        if not secret:
            return
        if isinstance(value, str):
            if secret in value:
                raise GatewayDenied("MODEL_RESPONSE_SECRET_DETECTED")
        elif isinstance(value, dict):
            for key, child in value.items():
                HTTPProviderAdapter._without_secret(key, secret)
                HTTPProviderAdapter._without_secret(child, secret)
        elif isinstance(value, (tuple, list)):
            for child in value:
                HTTPProviderAdapter._without_secret(child, secret)

    def _decode(self, payload, body):
        return ProviderResult.model_validate(body)

    def execute(self, model, payload):
        try:
            _, method, url, body, headers, secret, seconds, attempts, backoff, limit = (
                self._prepare(model, payload)
            )
            for attempt in range(attempts):
                try:
                    with httpx.Client(
                        transport=self.transport,
                        trust_env=False,
                        follow_redirects=False,
                        timeout=seconds,
                    ) as client:
                        with client.stream(method, url, json=body, headers=headers) as response:
                            response.raise_for_status()
                            raw = bytearray()
                            for part in response.iter_bytes():
                                raw.extend(part)
                                if len(raw) > limit:
                                    raise GatewayDenied("MODEL_RESPONSE_TOO_LARGE")
                            value = json.loads(raw)
                            self._without_secret(value, secret)
                            return self._decode(payload, value)
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
                    if attempt + 1 < attempts:
                        time.sleep(backoff)
                    else:
                        raise ProviderFailure() from None
        except GatewayDenied:
            raise
        except Exception:
            raise ProviderFailure() from None

    def _delta(self, body):
        return str(body["text_delta"])

    def stream(self, model, payload):
        try:
            _, method, url, body, headers, secret, seconds, _, _, limit = self._prepare(
                model, payload
            )
            buffer = ""
            total = 0
            with httpx.Client(
                transport=self.transport, trust_env=False, follow_redirects=False, timeout=seconds
            ) as client:
                with client.stream(method, url, json=body, headers=headers) as response:
                    response.raise_for_status()
                    # Enforce limits before decoding, including an unterminated line.
                    pending = b""
                    for part in response.iter_bytes():
                        total += len(part)
                        if total > limit:
                            raise GatewayDenied("MODEL_RESPONSE_TOO_LARGE")
                        pending += part
                        while b"\n" in pending:
                            line, pending = pending.split(b"\n", 1)
                            line = line.strip()
                            if not line.startswith(b"data:"):
                                continue
                            data = line[5:].strip()
                            if data == b"[DONE]":
                                if buffer:
                                    self._without_secret(buffer, secret)
                                    yield buffer
                                return
                            buffer += self._delta(json.loads(data))
                            self._without_secret(buffer, secret)
                            # Delay a possible secret prefix spanning multiple provider deltas.
                            retained = len(secret) - 1 if secret else 0
                            if len(buffer) > retained:
                                count = len(buffer) - retained
                                yield buffer[:count]
                                buffer = buffer[count:]
                    raise GatewayDenied("MODEL_STREAM_INCOMPLETE")
        except GatewayDenied:
            raise
        except Exception:
            raise ProviderFailure() from None


class OpenAICompatibleProviderAdapter(HTTPProviderAdapter):
    """A wire protocol, not an OpenAI model/provider choice."""

    supported_operations = frozenset(
        (
            ModelOperation.CHAT,
            ModelOperation.CHAT_STREAM,
            ModelOperation.STRUCTURED_OUTPUT,
            ModelOperation.EMBEDDING,
            ModelOperation.HEALTH_CHECK,
        )
    )

    def _wire(self, model, payload, connection):
        if payload.operation == ModelOperation.HEALTH_CHECK:
            return "GET", "/models", None
        if payload.operation == ModelOperation.EMBEDDING:
            return (
                "POST",
                "/embeddings",
                {"model": connection.model_name, "input": list(payload.texts)},
            )
        messages = (
            [{"role": "system", "content": payload.system_prompt}]
            if payload.system_prompt is not None
            else []
        )
        messages.extend({"role": "user", "content": t} for t in payload.texts)
        body = {
            "model": connection.model_name,
            "messages": messages,
            "max_tokens": payload.max_output_tokens,
        }
        if payload.operation == ModelOperation.CHAT_STREAM:
            body["stream"] = True
        if payload.operation == ModelOperation.STRUCTURED_OUTPUT:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_result",
                    "schema": payload.output_schema,
                    "strict": True,
                },
            }
        return "POST", "/chat/completions", body

    def _decode(self, payload, body):
        if payload.operation == ModelOperation.HEALTH_CHECK:
            return ProviderResult(healthy=isinstance(body.get("data"), list))
        if payload.operation == ModelOperation.EMBEDDING:
            rows = sorted(body["data"], key=lambda x: x["index"])
            if [r["index"] for r in rows] != list(range(len(payload.texts))):
                raise GatewayDenied("MODEL_RESULT_INVALID")
            return ProviderResult(embeddings=tuple(tuple(r["embedding"]) for r in rows))
        choice = body["choices"][0]
        if choice["message"].get("tool_calls") or choice.get("finish_reason") != "stop":
            raise GatewayDenied("MODEL_RESULT_INVALID")
        text = choice["message"]["content"]
        if payload.operation == ModelOperation.STRUCTURED_OUTPUT:
            return ProviderResult(structured=json.loads(text))
        return ProviderResult(text=text)

    def _delta(self, body):
        choice = body["choices"][0]
        if choice["delta"].get("tool_calls"):
            raise GatewayDenied("MODEL_RESULT_INVALID")
        return choice["delta"].get("content", "")

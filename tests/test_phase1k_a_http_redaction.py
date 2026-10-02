import json

import httpx
import pytest
from phase1k_a_fixtures import fixture

from crossborder_compliance.application.llm_gateway_redaction import (
    DataRedactionService,
    input_digest,
)
from crossborder_compliance.domain.llm_gateway import (
    DetectionResult,
    GatewayDenied,
    ProviderFailure,
    ProviderInput,
    SensitiveSpan,
)
from crossborder_compliance.infrastructure.llm_gateway_configuration import ProviderConnection
from crossborder_compliance.infrastructure.llm_gateway_http import (
    HTTPProviderAdapter,
    OpenAICompatibleProviderAdapter,
    check_endpoint,
)


class Connections:
    def __init__(self):
        self.settings = ProviderConnection(
            model_name="generic-model",
            endpoint={
                "url": "https://generic-model.invalid/v1",
                "paths": {"chat": "/invoke", "chat_stream": "/stream"},
            },
            secret_ref="secret://tenant/approved",
            auth_type="BEARER_SECRET_REF",
            timeout_policy={"seconds": 2},
            retry_policy={"max_attempts": 1},
            external=True,
        )

    def connection(self, model):
        return self.settings


class Secrets:
    def resolve(self, ref):
        assert ref == "secret://tenant/approved"
        return "FAKE-CREDENTIAL-987"


def adapter(handler, cls=HTTPProviderAdapter):
    return cls(
        Connections(),
        Secrets(),
        transport=httpx.MockTransport(handler),
        endpoint_check=lambda u, e: None,
    )


def payload(op="chat"):
    return ProviderInput(operation=op, texts=("already approved body",), max_output_tokens=512)


def test_generic_http_credential_resolved_only_inside_adapter(caplog):
    f = fixture()
    observed = []

    def handle(r):
        observed.append(r)
        assert r.headers["authorization"] == "Bearer FAKE-CREDENTIAL-987"
        return httpx.Response(200, json={"text": "safe response"})

    a = adapter(handle)
    result = a.execute(f["models"][0], payload())
    assert result.text == "safe response"
    assert "FAKE-CREDENTIAL-987" not in result.model_dump_json()
    assert "FAKE-CREDENTIAL-987" not in caplog.text
    assert "secret://tenant/approved" not in repr(a.connections.settings)
    assert len(observed) == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"location": "https://untrusted.invalid"}),
        httpx.Response(200, json={"text": "FAKE-CREDENTIAL-987"}),
        httpx.Response(200, content=b"x" * 1048577),
    ],
)
def test_redirects_secret_echo_and_oversized_response_are_blocked(response):
    calls = []
    a = adapter(lambda r: (calls.append(r), response)[1])
    with pytest.raises(Exception) as e:
        a.execute(fixture()["models"][0], payload())
    assert "FAKE-CREDENTIAL-987" not in str(e.value)
    assert len(calls) == 1


def test_retry_policy_is_registry_configuration_not_gateway_branch():
    calls = []
    a = adapter(lambda r: (calls.append(r), httpx.Response(503))[1])
    old = a.connections.settings
    from dataclasses import replace

    a.connections.settings = replace(old, retry_policy={"max_attempts": 2, "backoff_seconds": 0})
    with pytest.raises((GatewayDenied, ProviderFailure)):
        a.execute(fixture()["models"][0], payload())
    assert len(calls) == 2


@pytest.mark.parametrize(
    "op,body",
    [
        ("chat", {"choices": [{"message": {"content": "safe"}, "finish_reason": "stop"}]}),
        ("embedding", {"data": [{"index": 0, "embedding": [1.0, 0.0]}]}),
        (
            "structured_output",
            {"choices": [{"message": {"content": '{"value":"ok"}'}, "finish_reason": "stop"}]},
        ),
        ("health_check", {"data": []}),
    ],
)
def test_openai_compatible_wire_without_specific_provider_sdk(op, body):
    observed = []
    a = adapter(
        lambda r: (observed.append(r), httpx.Response(200, json=body))[1],
        OpenAICompatibleProviderAdapter,
    )
    a.execute(
        fixture()["models"][0], payload(op).model_copy(update={"output_schema": {"type": "object"}})
    )
    assert len(observed) == 1
    if op == "chat":
        assert json.loads(observed[0].content)["messages"][0]["role"] == "user"


def test_openai_does_not_claim_unsupported_rerank_or_token_count():
    calls = []
    a = adapter(lambda r: calls.append(r), OpenAICompatibleProviderAdapter)
    with pytest.raises(GatewayDenied):
        a.execute(fixture()["models"][0], payload("rerank"))
    with pytest.raises(GatewayDenied):
        a.execute(fixture()["models"][0], payload("count_tokens"))
    assert not calls


def test_stream_blocks_secret_split_across_deltas():
    body = (
        'data: {"text_delta":"FAKE-CRED"}\n\ndata: {"text_delta":"ENTIAL-987"}\n\ndata: [DONE]\n\n'
    )
    a = adapter(lambda r: httpx.Response(200, content=body))
    out = []
    with pytest.raises(GatewayDenied):
        for delta in a.stream(fixture()["models"][0], payload("chat_stream")):
            out.append(delta)
    assert not out


def test_stream_success_and_incomplete_stream_detection():
    a = adapter(
        lambda r: httpx.Response(200, content='data: {"text_delta":"ok"}\n\ndata: [DONE]\n\n')
    )
    assert "".join(a.stream(fixture()["models"][0], payload("chat_stream"))) == "ok"
    a = adapter(lambda r: httpx.Response(200, content='data: {"text_delta":"partial"}\n\n'))
    with pytest.raises(GatewayDenied, match="MODEL_STREAM_INCOMPLETE"):
        list(a.stream(fixture()["models"][0], payload("chat_stream")))


@pytest.mark.parametrize(
    "url",
    [
        "http://public.invalid",
        "https://user:secret@public.invalid",
        "https://public.invalid/?api_key=secret",
        "https://public.invalid/#secret",
    ],
)
def test_invalid_external_endpoint_denied_before_dns_or_auth(url):
    with pytest.raises(GatewayDenied):
        check_endpoint(url, True)


def test_external_dns_private_ip_denied(monkeypatch):
    monkeypatch.setattr(
        "socket.getaddrinfo", lambda *a: [(None, None, None, None, ("127.0.0.1", 443))]
    )
    with pytest.raises(GatewayDenied):
        check_endpoint("https://rebind.invalid", True)


def test_overlapping_sensitive_ranges_mask_union_and_omit_raw_dto():
    class Detector:
        def detect(self, texts):
            return DetectionResult(
                input_hash=input_digest(texts),
                complete=True,
                spans=(
                    SensitiveSpan(part_index=0, start=1, end=5, sensitive_type="A"),
                    SensitiveSpan(part_index=0, start=3, end=7, sensitive_type="B"),
                ),
            )

    f = fixture()
    texts = ("xPRIVATEz",)
    r = DataRedactionService(Detector()).redact(texts, (f["ref"],), (f["policies"][0].version_id,))
    assert len(r.redacted_ranges) == 1 and r.redacted_ranges[0].end == 7
    assert r.detected_sensitive_types == ("A", "B") and not r.reversible
    assert "PRIVATE" not in r.model_dump_json() and "redacted_texts" not in r.model_dump()
    assert texts == ("xPRIVATEz",)


@pytest.mark.parametrize("kind", ("hash", "range"))
def test_detector_wrong_input_hash_or_invalid_range_fail_closed(kind):
    class Detector:
        def detect(self, texts):
            return DetectionResult(
                input_hash="wrong" if kind == "hash" else input_digest(texts),
                complete=True,
                spans=(SensitiveSpan(part_index=0, start=0, end=999, sensitive_type="A"),),
            )

    f = fixture()
    with pytest.raises(GatewayDenied):
        DataRedactionService(Detector()).redact(("body",), (f["ref"],), ())

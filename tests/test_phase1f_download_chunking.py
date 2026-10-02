import hashlib
import io

import pytest

from crossborder_compliance.application.knowledge_services import StructureAwareChunkingStrategy
from crossborder_compliance.domain.knowledge import KnowledgeStructureNode
from crossborder_compliance.infrastructure.knowledge_download import ControlledHTTPSDownloader


class Response:
    def __init__(self, status=200, headers=None, body=b'{"nodes":[]}'):
        self.status = status
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.body = io.BytesIO(body)

    def getheader(self, name):
        return self.headers.get(name)

    def read(self, size):
        return self.body.read(size)


class Connection:
    def __init__(self, response):
        self.response = response
        self.closed = False
        self.requested = None

    def request(self, *args, **kwargs):
        self.requested = (args, kwargs)

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


def downloader(responses=None, ip="93.184.216.34", **kw):
    responses = iter(responses or [Response()])
    connections = []
    calls = []

    def factory(host, address, timeout):
        conn = Connection(next(responses))
        connections.append(conn)
        calls.append((host, address, timeout))
        return conn

    d = ControlledHTTPSDownloader(
        {"generic.example"},
        resolver=lambda *a, **k: [(0, 0, 0, "", (ip, 443))],
        connection_factory=factory,
        **kw,
    )
    return d, connections, calls


@pytest.mark.parametrize(
    "url",
    [
        "http://generic.example/x",
        "https://generic.example:80/x",
        "https://u:p@generic.example/x",
        "https://generic.example/x#fragment",
        "https://other.example/x",
        "https://generic.example/\\x",
        "https://generic.example/x",
        "file:///etc/passwd",
    ],
)
def test_controlled_protocol_host_policy(url):
    d, connections, _ = downloader()
    with pytest.raises(ValueError):
        d.download(url)
    assert not connections


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "192.168.1.1",
        "::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "224.0.0.1",
    ],
)
def test_controlled_private_dns_policy(ip):
    d, connections, _ = downloader(ip=ip)
    with pytest.raises(ValueError, match="PRIVATE_IP_BLOCKED"):
        d.download("https://generic.example/x")
    assert not connections


@pytest.mark.parametrize(
    "response",
    [
        Response(status=500),
        Response(headers={"Content-Type": "text/html"}),
        Response(headers={"Content-Encoding": "gzip"}),
        Response(headers={"Content-Length": "10000001"}),
        Response(headers={"Content-Length": "100"}),
        Response(body=b"123456789"),
    ],
)
def test_controlled_mime_size_encoding_truncation(response):
    d, connections, _ = downloader([response], max_size=8)
    with pytest.raises(ValueError):
        d.download("https://generic.example/x")
    assert connections[0].closed


def test_controlled_pinned_dns_hash_audit_redirect():
    d, connections, calls = downloader(
        [Response(status=302, headers={"Location": "/new"}), Response(body=b"{}")]
    )
    content, audit = d.download("https://generic.example/x")
    assert content == b"{}" and audit["content_hash"] == hashlib.sha256(content).hexdigest()
    assert (
        len(audit["request_audit"]) == 2
        and all(call[1] == "93.184.216.34" for call in calls)
        and all(c.closed for c in connections)
    )
    assert connections[1].requested[0][1] == "/new"


def test_controlled_redirect_revalidation_and_limit():
    d, connections, _ = downloader(
        [Response(status=302, headers={"Location": "https://127.0.0.1/x"})]
    )
    with pytest.raises(ValueError):
        d.download("https://generic.example/x")
    assert len(connections) == 1 and connections[0].closed
    d, _, _ = downloader([Response(status=302, headers={"Location": "/again"})], redirect_limit=0)
    with pytest.raises(ValueError, match="REDIRECT_LIMIT"):
        d.download("https://generic.example/x")


def test_controlled_mixed_dns_and_timeout():
    d, connections, _ = downloader()
    d.resolver = lambda *a, **kw: [
        (0, 0, 0, "", ("93.184.216.34", 443)),
        (0, 0, 0, "", ("10.0.0.1", 443)),
    ]
    with pytest.raises(ValueError):
        d.download("https://generic.example/x")
    assert not connections
    d, _, _ = downloader(timeout=0)
    with pytest.raises(TimeoutError):
        d.download("https://generic.example/x")


def node(ident, type_, text):
    return KnowledgeStructureNode(
        structure_node_id=ident,
        knowledge_version_id="v",
        node_type=type_,
        sequence=0,
        canonical_locator=ident,
        original_text=text,
        normalized_text=text,
        language="en",
        source_trace={"fixture": True},
        provenance={"fixture": True},
        citation_id="citation-" + ident,
    )


def test_chunking_preserves_canonical_boundaries():
    nodes = [
        node("a", "ARTICLE", " ".join(["word"] * 600)),
        node("b", "SECTION", "section original text"),
    ]
    strategy = StructureAwareChunkingStrategy()
    chunks = strategy.chunk(nodes, "STRUCTURE_AWARE")
    assert (
        len(chunks) == 2 and chunks[0].token_count == 600 and chunks[0].structure_node_ids == ("a",)
    )
    sliding = strategy.chunk(nodes, "SLIDING_WINDOW")
    assert len(sliding) == 4 and all(len(ch.structure_node_ids) == 1 for ch in sliding)
    assert len(strategy.chunk(nodes, "ARTICLE")) == 1 and len(strategy.chunk(nodes, "SECTION")) == 1
    with pytest.raises(ValueError):
        strategy.chunk(nodes, "UNKNOWN")

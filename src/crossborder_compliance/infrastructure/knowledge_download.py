"""Controlled HTTPS transport. DNS results are validated and pinned per redirect."""

import hashlib
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


class ControlledHTTPSDownloader:
    def __init__(
        self,
        allowed_hosts,
        *,
        timeout=15,
        max_size=10_000_000,
        redirect_limit=3,
        resolver=socket.getaddrinfo,
        connection_factory=PinnedHTTPSConnection,
    ):
        self.allowed_hosts = frozenset(h.lower() for h in allowed_hosts)
        self.timeout, self.max_size, self.redirect_limit = timeout, max_size, redirect_limit
        self.resolver, self.connection_factory = resolver, connection_factory

    def download(self, url):
        original = url
        deadline = time.monotonic() + self.timeout
        audit = []
        for hop in range(self.redirect_limit + 1):
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.port not in {None, 443}
                or parsed.username
                or parsed.password
                or parsed.fragment
                or "\\" in url
                or any(ord(ch) < 33 for ch in url)
            ):
                raise ValueError("HTTPS_POLICY")
            host = parsed.hostname.lower()
            if host not in self.allowed_hosts:
                raise ValueError("HOST_NOT_APPROVED")
            addresses = [item[4][0] for item in self.resolver(host, 443, type=socket.SOCK_STREAM)]
            if not addresses:
                raise ValueError("DNS_EMPTY")
            for address in addresses:
                ip = ipaddress.ip_address(address)
                ip = getattr(ip, "ipv4_mapped", None) or ip
                if not ip.is_global or ip.is_multicast:
                    raise ValueError("PRIVATE_IP_BLOCKED")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("DOWNLOAD_TIMEOUT")
            conn = self.connection_factory(host, addresses[0], remaining)
            try:
                conn.request(
                    "GET",
                    (parsed.path or "/") + ("?" + parsed.query if parsed.query else ""),
                    headers={
                        "Host": host,
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                    },
                )
                response = conn.getresponse()
                audit.append(
                    {"host": host, "validated_ip": addresses[0], "status": response.status}
                )
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if not location or hop == self.redirect_limit:
                        raise ValueError("REDIRECT_LIMIT")
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    raise ValueError("HTTP_STATUS")
                if (response.getheader("Content-Type") or "").split(";")[
                    0
                ].strip().lower() != "application/json":
                    raise ValueError("MIME_POLICY")
                if response.getheader("Content-Encoding") not in {None, "identity"}:
                    raise ValueError("CONTENT_ENCODING_POLICY")
                declared = response.getheader("Content-Length")
                if declared is not None and (int(declared) < 0 or int(declared) > self.max_size):
                    raise ValueError("MAX_FILE_SIZE")
                parts = []
                size = 0
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("DOWNLOAD_TIMEOUT")
                    if getattr(conn, "sock", None):
                        conn.sock.settimeout(remaining)
                    part = response.read(min(65536, self.max_size - size + 1))
                    if not part:
                        break
                    size += len(part)
                    if size > self.max_size:
                        raise ValueError("MAX_FILE_SIZE")
                    parts.append(part)
                content = b"".join(parts)
                if declared is not None and len(content) != int(declared):
                    raise ValueError("TRUNCATED_DOWNLOAD")
                return content, {
                    "source_hash": hashlib.sha256(original.encode()).hexdigest(),
                    "content_hash": hashlib.sha256(content).hexdigest(),
                    "request_audit": audit,
                }
            finally:
                conn.close()
        raise ValueError("REDIRECT_LIMIT")

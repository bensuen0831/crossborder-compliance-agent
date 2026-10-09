"""Northbound callback transport with DNS pinning and authenticated envelopes."""
import hashlib
import hmac
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlparse

from crossborder_compliance.application.integrations import IntegrationFailure
from crossborder_compliance.infrastructure.llm_gateway_http import check_endpoint


def callback_addresses(url,deployment_class,internal_hosts=()):
    parsed=urlparse(url)
    if '\\' in url or any(ord(c)<33 for c in url):raise IntegrationFailure('INVALID_INPUT',422)
    if deployment_class=='INTERNAL' and parsed.hostname not in internal_hosts:
        raise IntegrationFailure('FORBIDDEN')
    try:
        check_endpoint(url,deployment_class=='EXTERNAL')
        ips=tuple(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(
            parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM)))
        if not ips:raise ValueError()
        for value in ips:
            ip=ipaddress.ip_address(value);ip=getattr(ip,'ipv4_mapped',None) or ip
            if ip.is_link_local or ip.is_multicast or ip.is_unspecified or (deployment_class=='EXTERNAL' and not ip.is_global):
                raise ValueError()
    except Exception:raise IntegrationFailure('INVALID_INPUT',422) from None
    return parsed,ips


def signature(secret,delivery_id,timestamp,body):
    message=delivery_id.encode()+b'.'+str(timestamp).encode()+b'.'+body
    return 'sha256='+hmac.new(secret.encode(),message,hashlib.sha256).hexdigest()


def verify_signature(secret,delivery_id,timestamp,body,supplied,*,now,max_skew_seconds=300,seen_delivery_ids=None):
    try:
        valid=abs(int(now)-int(timestamp))<=max_skew_seconds
        valid=valid and hmac.compare_digest(signature(secret,delivery_id,timestamp,body),supplied)
        valid=valid and (seen_delivery_ids is None or delivery_id not in seen_delivery_ids)
        if valid and seen_delivery_ids is not None:seen_delivery_ids.add(delivery_id)
        return valid
    except (ValueError,TypeError):return False


def post_callback(url,deployment_class,internal_hosts,body,headers,timeout):
    parsed,ips=callback_addresses(url,deployment_class,internal_hosts)
    # Connect to the already validated IP. TLS still verifies the original
    # hostname, preventing DNS rebind between validation and connection.
    port=parsed.port or (443 if parsed.scheme=='https' else 80)
    connection=http.client.HTTPConnection(parsed.hostname,port,timeout=timeout)
    sock=socket.create_connection((ips[0],port),timeout=timeout)
    if parsed.scheme=='https':
        try:sock=ssl.create_default_context().wrap_socket(sock,server_hostname=parsed.hostname)
        except Exception:sock.close();raise
    connection.sock=sock
    try:
        connection.request('POST',parsed.path or '/',body=body,headers=headers)
        response=connection.getresponse()
        # Response bodies are not evidence, metadata or logs; bounded read only.
        response.read(4096)
        return response.status
    finally:connection.close()

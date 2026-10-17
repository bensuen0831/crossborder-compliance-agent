"""S3 multipart with versioned, streaming verification; no whole-file byte buffers."""

import base64
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit

import boto3
import botocore.session
from botocore.config import Config
from botocore.exceptions import ClientError

from crossborder_compliance.domain.knowledge_upload import SHA256_PATTERN


class S3KnowledgeBinaryStore:
    def __init__(
        self, *, endpoint_url, bucket, access_key, secret_key, region="us-east-1", client=None
    ):
        endpoint = urlsplit(endpoint_url)
        if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ValueError("UNSAFE_S3_ENDPOINT")
        local = endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
        if endpoint.scheme != "https" and not (local and endpoint.scheme == "http"):
            raise ValueError("S3_ENDPOINT_REQUIRES_TLS")
        self.bucket = bucket
        session = boto3
        if local and client is None:
            # An explicitly credentialed local service is not an AWS identity.
            # Keep the managed cloud's global profile/environment untouched.
            core = botocore.session.Session(session_vars={"profile": (None, None, None, None)})
            session = boto3.Session(botocore_session=core)
        self.client = client or session.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=10,
                read_timeout=120,
                **({"proxies": {}} if local else {}),
            ),
        )

    @staticmethod
    def _key(key):
        if (
            not key.startswith("knowledge-upload/")
            or any(p in {"", ".", ".."} for p in key.split("/"))
            or "\\" in key
        ):
            raise ValueError("UNSAFE_KNOWLEDGE_OBJECT_KEY")
        return key

    def begin(self, key, content_type):
        if self.client.get_bucket_versioning(Bucket=self.bucket).get("Status") != "Enabled":
            raise ValueError("S3_OBJECT_VERSIONING_REQUIRED")
        pending = [
            item
            for page in self.client.get_paginator("list_multipart_uploads").paginate(
                Bucket=self.bucket, Prefix=self._key(key)
            )
            for item in page.get("Uploads", [])
            if item["Key"] == key
        ]
        if len(pending) > 1:
            raise ValueError("AMBIGUOUS_OWNED_MULTIPART_UPLOAD")
        if pending:
            return pending[0]["UploadId"]
        return self.client.create_multipart_upload(
            Bucket=self.bucket, Key=self._key(key), ContentType=content_type
        )["UploadId"]

    def abort_pending(self, key):
        """Recover only exact server-owned intents after a lost create response."""
        key = self._key(key)
        for page in self.client.get_paginator("list_multipart_uploads").paginate(
            Bucket=self.bucket, Prefix=key
        ):
            for upload in page.get("Uploads", []):
                if upload["Key"] == key:
                    self.abort(key, upload["UploadId"])

    def part_url(self, key, upload_id, number, size, sha256, expiry):
        if (
            not 1 <= number <= 10000
            or size < 1
            or not SHA256_PATTERN.fullmatch(sha256)
            or not 1 <= expiry <= 3600
        ):
            raise ValueError("INVALID_UPLOAD_PART")
        checksum = base64.b64encode(bytes.fromhex(sha256)).decode()
        url = self.client.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": self.bucket,
                "Key": self._key(key),
                "UploadId": upload_id,
                "PartNumber": number,
                "ContentLength": size,
                "ChecksumSHA256": checksum,
            },
            ExpiresIn=expiry,
            HttpMethod="PUT",
        )
        return {"url": url, "headers": {"x-amz-checksum-sha256": checksum}, "byte_size": size}

    def parts(self, key, upload_id):
        result = []
        for page in self.client.get_paginator("list_parts").paginate(
            Bucket=self.bucket, Key=self._key(key), UploadId=upload_id
        ):
            result.extend(
                {"number": p["PartNumber"], "byte_size": p["Size"], "etag": p["ETag"]}
                for p in page.get("Parts", [])
            )
        return result

    def complete(self, key, upload_id, parts):
        try:
            result = self.client.complete_multipart_upload(
                Bucket=self.bucket,
                Key=self._key(key),
                UploadId=upload_id,
                MultipartUpload={
                    "Parts": [
                        {"PartNumber": p["number"], "ETag": p["etag"]}
                        for p in sorted(parts, key=lambda p: p["number"])
                    ]
                },
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchUpload":
                raise
            # A crash after S3 completion can lose the response, not the owned object.
            return self.head(key)
        if not result.get("VersionId"):
            raise ValueError("S3_OBJECT_VERSION_ID_REQUIRED")
        return self.head(key)

    def head(self, key):
        result = self.client.head_object(Bucket=self.bucket, Key=self._key(key))
        if not result.get("VersionId") or result["VersionId"] == "null":
            raise ValueError("S3_OBJECT_VERSION_ID_REQUIRED")
        return {
            "object_version": result["VersionId"],
            "byte_size": result["ContentLength"],
            "storage_ref": f"s3://{self.bucket}/{key}",
        }

    def download(self, key, version, target: Path, max_bytes):
        if not version or version == "null" or max_bytes <= 0:
            raise ValueError("EXACT_S3_OBJECT_VERSION_REQUIRED")
        body = self.client.get_object(Bucket=self.bucket, Key=self._key(key), VersionId=version)[
            "Body"
        ]
        total, digest = 0, hashlib.sha256()
        try:
            with target.open("xb") as output:
                while chunk := body.read(8 * 1024**2):
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("KNOWLEDGE_OBJECT_SIZE_LIMIT")
                    output.write(chunk)
                    digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        finally:
            body.close()
        return {"byte_size": total, "content_sha256": digest.hexdigest()}

    def abort(self, key, upload_id):
        try:
            self.client.abort_multipart_upload(
                Bucket=self.bucket, Key=self._key(key), UploadId=upload_id
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchUpload":
                raise

    def delete(self, key, version):
        if not version or version == "null":
            raise ValueError("EXACT_S3_OBJECT_VERSION_REQUIRED")
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key), VersionId=version)

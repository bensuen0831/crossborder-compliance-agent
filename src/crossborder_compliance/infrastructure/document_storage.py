from __future__ import annotations

from urllib.parse import urlparse
import boto3


class S3ObjectStorageAdapter:
    """Object-storage adapter; DB/LangGraph never receive original binary bytes."""

    def __init__(self, *, endpoint_url: str, bucket: str, access_key: str, secret_key: str):
        self.bucket=bucket
        self.client=boto3.client("s3",endpoint_url=endpoint_url,aws_access_key_id=access_key,aws_secret_access_key=secret_key)

    def put(self, *, object_key: str, content: bytes, content_type: str) -> str:
        if object_key.startswith("/") or ".." in object_key.split("/"):
            raise ValueError("unsafe object key")
        self.client.put_object(Bucket=self.bucket,Key=object_key,Body=content,ContentType=content_type)
        return f"s3://{self.bucket}/{object_key}"

    def get(self, storage_ref: str) -> bytes:
        parsed=urlparse(storage_ref)
        if parsed.scheme!="s3" or parsed.netloc!=self.bucket:
            raise ValueError("storage_ref outside configured bucket")
        key=parsed.path.lstrip("/")
        if not key or ".." in key.split("/"): raise ValueError("unsafe storage_ref")
        return self.client.get_object(Bucket=self.bucket,Key=key)["Body"].read()

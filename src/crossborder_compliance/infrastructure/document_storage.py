from __future__ import annotations

from urllib.parse import urlparse
import boto3
import hashlib
import os
from pathlib import Path


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


class FileObjectStorageAdapter:
    """Configured durable local/restricted storage behind ObjectStoragePort.

    Refs are opaque object keys, never browser paths. Content-addressed writes
    are exclusive and verified; symlink/path escapes fail closed.
    """
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key):
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise ValueError("unsafe object reference")
        target = self.root / key
        if not target.resolve().is_relative_to(self.root):
            raise ValueError("storage ownership escape")
        return target

    def put(self, *, object_key, content, content_type):
        target=self._path(object_key)
        target.parent.mkdir(parents=True,exist_ok=True)
        # Atomic publish avoids an interrupted write becoming a valid object.
        import tempfile
        fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=".upload-")
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(content); f.flush(); os.fsync(f.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                if hashlib.sha256(self.get("object://local/"+object_key)).digest()!=hashlib.sha256(content).digest():
                    raise ValueError("immutable binary collision")
        finally:
            os.unlink(temporary)
        return "object://local/"+object_key

    def get(self, storage_ref):
        parsed=urlparse(storage_ref)
        if parsed.scheme!="object" or parsed.netloc!="local" or parsed.query or parsed.fragment:
            raise ValueError("storage reference outside configured adapter")
        target=self._path(parsed.path.lstrip("/"))
        fd=os.open(target,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,"rb") as f: return f.read()

"""Encrypted private local secret adapter; key provisioning is deployment-owned."""

import os
import stat
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.fernet import Fernet

from crossborder_compliance.domain.llm_gateway import GatewayDenied


class EncryptedFileSecretStore:
    def __init__(self, root, key, tenant_id):
        self.tenant_id = UUID(str(tenant_id))
        try:
            self.cipher = Fernet(key)
            parent = Path(root)
            if not parent.is_absolute() or parent.is_symlink():
                raise ValueError()
            parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.root = parent / str(self.tenant_id)
            self.root.mkdir(mode=0o700, exist_ok=True)
            for path in (parent, self.root):
                info = path.lstat()
                if (
                    not stat.S_ISDIR(info.st_mode)
                    or info.st_mode & 0o077
                    or info.st_uid != os.getuid()
                ):
                    raise ValueError()
        except Exception:
            raise GatewayDenied("SECRET_UNAVAILABLE") from None

    def put(self, value):
        try:
            if (
                not isinstance(value, str)
                or not 1 <= len(value) <= 8192
                or "\n" in value
                or "\r" in value
            ):
                raise ValueError()
            identity = uuid4()
            ciphertext = self.cipher.encrypt(value.encode())
            fd = os.open(
                self.root / str(identity),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(fd, "wb") as handle:
                handle.write(ciphertext)
                handle.flush()
                os.fsync(handle.fileno())
            return f"secret://{self.tenant_id}/{identity}"
        except Exception:
            raise GatewayDenied("SECRET_UNAVAILABLE") from None

    def resolve(self, secret_ref):
        try:
            prefix = f"secret://{self.tenant_id}/"
            if not secret_ref.startswith(prefix):
                raise ValueError()
            identity = UUID(secret_ref[len(prefix) :])
            fd = os.open(self.root / str(identity), os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as handle:
                info = os.fstat(handle.fileno())
                if info.st_mode & 0o077 or info.st_uid != os.getuid() or info.st_size > 16384:
                    raise ValueError()
                return self.cipher.decrypt(handle.read(16384)).decode()
        except Exception:
            raise GatewayDenied("SECRET_UNAVAILABLE") from None

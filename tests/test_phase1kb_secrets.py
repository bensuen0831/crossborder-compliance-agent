from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from crossborder_compliance.domain.llm_gateway import GatewayDenied
from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore


def test_encrypted_not_plaintext_reference_scope_and_restart(tmp_path):
    tenant, key = uuid4(), Fernet.generate_key()
    store = EncryptedFileSecretStore(tmp_path / "protected", key, tenant)
    reference = store.put("write-only-private-value")
    assert "write-only-private-value" not in reference
    assert b"write-only-private-value" not in next(store.root.iterdir()).read_bytes()
    assert (
        EncryptedFileSecretStore(tmp_path / "protected", key, tenant).resolve(reference)
        == "write-only-private-value"
    )
    with pytest.raises(GatewayDenied, match="SECRET_UNAVAILABLE"):
        EncryptedFileSecretStore(tmp_path / "protected", key, uuid4()).resolve(reference)


def test_missing_key_untrusted_permissions_and_symlink_fail_closed(tmp_path):
    root = tmp_path / "bad"
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    with pytest.raises(GatewayDenied, match="SECRET_UNAVAILABLE"):
        EncryptedFileSecretStore(root, Fernet.generate_key(), uuid4())
    with pytest.raises(GatewayDenied, match="SECRET_UNAVAILABLE"):
        EncryptedFileSecretStore(tmp_path / "new", b"invalid-key", uuid4())
    link = tmp_path / "link"
    link.symlink_to(root)
    with pytest.raises(GatewayDenied, match="SECRET_UNAVAILABLE"):
        EncryptedFileSecretStore(link, Fernet.generate_key(), uuid4())


@pytest.mark.parametrize("value", ["", "bad\nvalue", "bad\rvalue", "x" * 8193])
def test_invalid_secret_never_echoed(tmp_path, value):
    store = EncryptedFileSecretStore(tmp_path / "store", Fernet.generate_key(), uuid4())
    with pytest.raises(GatewayDenied) as error:
        store.put(value)
    assert str(error.value) == "SECRET_UNAVAILABLE"

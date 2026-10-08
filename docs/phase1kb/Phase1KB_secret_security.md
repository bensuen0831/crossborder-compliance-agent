# Secret boundary

Application `SecretStorePort` extends the K-A resolver with write-only `put`; metadata stores only an immutable opaque reference. The local infrastructure adapter encrypts each credential with Fernet, requires an externally provisioned encryption key and absolute protected root, checks owner/private permissions and rejects symlinks. Files are0600, directories0700; values never enter normal PostgreSQL metadata. Restart resolution reuses the configured key. No automatic key generation or plaintext fallback exists. Cloud/vault deployments supply this same port; no production vault is falsely claimed configured.

Admin authorization, ownership/concurrency and endpoint validation run before a credential write. Replacement creates a new reference and provider version; historical references remain distinct. API responses and audit are allowlisted. Provider exceptions are sanitized; raw HTTP bodies/credentials do not escape. Provider response credential echoes remain denied by the canonical HTTP adapter.

Focused tests cover ciphertext at rest, restart, cross-tenant secret rejection, missing key, insecure directory, symlink and invalid values, plus provider replacement and no normal metadata/GET exposure. Browser storage/log/artifact checks belong to later closure gates; this document does not claim they have run.

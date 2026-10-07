# M2B api contract

Existing `/api/v1/projects/{project_id}/intake` convention is extended with GET documents/policy, GET documents (optional historical version), multipart POST documents, POST documents/{version_id}/parse and /unlink, and POST supersede. Pydantic forbids client authority fields; response DTOs are generated through the existing m2a OpenAPI pipeline. Current server context reauthorizes every operation. Concurrent versions return409; ordinary missing capability503; readiness validation422. No binary-in-JSON contract.

# Runtime publication UI result

For an `ACTIVE` Knowledge version, the feature polls `GET /api/v1/admin/knowledge-versions/{id}/runtime-readiness`. It renders `PENDING`, `BUILDING`, `READY` or `FAILED` and the server's registry, FTS, embedding/vector, graph and cache checks, projection/cache identifiers, asset evidence and reason codes. Missing checks say “Not reported”; a no-embedding configuration is not falsely claimed to have generated vectors.

Publishing does not optimistically mark runtime READY. Failures remain visible while the existing outbox worker retries. Polling stops on READY or an access/service error and cancels when the component unmounts. No undocumented retry/reindex operation is offered. Metadata registry publication has no comparable runtime readiness endpoint and is not given a fabricated status.

Frontend tests cover READY, missing checks and FAILED reason codes. A real API integration test publishes after independent approval, waits for the automatic background consumer to reach READY, asserts every returned readiness check, and retrieves the newly published content through the project runtime query endpoint. Existing Phase 1G tests continue to cover vector/index failures and idempotent outbox recovery.

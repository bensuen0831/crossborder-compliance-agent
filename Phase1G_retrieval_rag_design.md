# Phase 1G design

Phase: **1G — Scope-first Hybrid Retrieval / RAG foundation + Publish-driven Runtime Synchronization**.

Implementation tested PR head SHA: `beeaa0a692e97a8554e3247f6a53bf5dc23f9f0f`. Runner merge SHA: `887029e59b3bea94925be7fb0a0ddf530e59de75`.
GitHub Actions Run ID: **36989359103**, Run Number: **100**, Attempt: **1**, conclusion **SUCCESS**.
Artifact ID: **11218543793**; digest `sha256:a6c70f27ef45e3cec242b5ef6927b4faf1ca9021c6b0dde4e1d379b77442cee3`.
Remote full gate log SHA-256: `d44a8b7d3797ae03dc9d042cb9b3ce5f3fefc28082fa9298217da3ebbb7a511f`; `ci_complete.log` is retained inside that GitHub artifact.

Measured full pytest: **200 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**. Alembic head: **0007_phase1g**.
Schema assertions: Phase 1B **16/16**, 1C **20/20**, 1D **15/15**, 1E **22/22**, 1F **29/29**, 1G **58/58 PASS**.
Executable architecture checks: **108/108 PASS**; Phase 1A runtime assertions: **25/25 PASS**. Phase 1A–1F regressions: **PASS**.

Evidence: [verified remote identity](evidence/phase1g/implementation-ci/verified_identity.json), [measured remote summary](evidence/phase1g/implementation-ci/empirical_summary.json), [local complete gate log](evidence/phase1g/local-final/ci_complete.log).
This implementation CI is distinct from the subsequent documentation-only closure head. The formal closure CI and issuance identities are recorded in [Phase1H_entry_decision.md](Phase1H_entry_decision.md) only after that head passes complete CI; this document does not authorize Phase 1H coding.

## Actual pipeline

`FormalContext (1E) → KnowledgeScopeResolver / KnowledgeFilterSpec (1F) → snapshot-pinned RetrievalPolicy → tenant/permission/lifecycle/version/date/product/jurisdiction/scenario/industry/data-category/language filters → MATERIALIZED FTS/pgvector candidate set → deterministic hybrid → optional allowed-set rerank / reviewed graph expansion → fresh scope revalidation → internal EvidencePack → policy sufficiency → permitted controlled external augmentation → reassessment → RAGContextPack + fallback guidance`.

The API accepts project/snapshot/policy/query/subject/languages/idempotency only. It cannot accept a custom scope. Similarity cannot alter legal sufficiency. Explicit approved evidence conflicts remain CONFLICTED and retain guidance, without selecting a legal truth.

## Publication-driven runtime availability

The existing Phase 1F Publish transaction inserts `KNOWLEDGE_VERSION_PUBLISHED` into Phase 1C `registry_sync_events` and a PENDING derived publication row atomically. FastAPI lifespan starts `KnowledgePublicationWorker`; it dispatches through the existing `RegistrySyncService` consumer hook. A tenant/document advisory lease serializes duplicate builds. Registry refresh, canonical FTS/index build, optional registry-resolved embedding/vector materialization, exact canonical Graph projection, monotonic Redis cache generation and readiness validation precede READY.

New retrieval scope requires ACTIVE and READY. Failed new publication is fail-closed for new snapshots. Previously READY assets and existing approved historical snapshot pins remain usable; a snapshot that froze an empty allowed universe is never refreshed silently after retry. A new analysis must create a new snapshot after READY. No admin Sync/Reindex operation is required in the normal publication path.

When vector publication is configured, an EmbeddingPort must be installed by server configuration; absent or failing ports keep the version NOT READY and retry through the durable outbox. Real providers remain a future Gateway responsibility. Conflicting active embedding configs fail closed.

## Reused foundations / actual sources

- Domain: `domain/retrieval.py`; application: `retrieval_services.py`, `retrieval_algorithms.py`, `external_evidence_services.py`, `knowledge_runtime_services.py`.
- Existing formal context/scope, registry/model metadata, canonical evidence/citation, index/embedding lifecycle and durable Admin review are reused.
- `retrieval_search.py` contains the parameterized MATERIALIZED hard-filter CTE and actual PostgreSQL operators.
- `0007_phase1g_retrieval_evidence.py` adds 19 derived/governance tables. No duplicate canonical chunk/document or event store is created.

PASS assertions are exercised by all `tests/test_phase1g_*`, including the 12 publication tests and 36 original mandatory case mappings in `test_result.md`.

## Boundaries / exclusions / regression status

Phase 1E formal Context remains the only context input. Phase 1F PostgreSQL Source/Document/Version/Structure/Chunk/Binding/EvidenceReference/Citation tables remain canonical Knowledge Source of Truth. Retrieval stores, runtime materialization state, indexes, Wiki/Graph and RAGContextPack are derived. Runtime external evidence remains VERIFIED, separate from ACTIVE canonical knowledge.

Excluded: production model/provider execution, LLM answers, formal classification, regulation applicability, country-specific compliance routing, risk, Candidate/Final Compliance Path, required regulatory-document decisions and production legal agents. External parsing currently accepts attributed canonical JSON through the existing controlled MIME boundary; HTML/PDF web crawling and unrestricted discovery are outside this foundation. Embedding/rerank tests use explicit deterministic adapters behind ports. Original source text is preserved; no reviewed translation becomes original official text.

Phase 1A–1F regressions pass under the current 0007 migration. Earlier migration files 0001–0006 are unchanged. The historical Phase 1F main baseline remains `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95`; its 142-test baseline is historical and is not substituted for this Phase 1G 200-test result.

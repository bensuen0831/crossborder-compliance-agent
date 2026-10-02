# Phase 1G test result

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

## Measured suite / required case mapping

The mandatory gate runs full pytest with no `-m`, skip or deselect. Contract/static CI is an additional job; it does not replace the full PostgreSQL/LangGraph job. `verify_full_pytest.py` rejects failure/error/skip/deselect or missing Phase 1B–1G coverage.

Phase 1G contributes **58 tests**; the existing **142-test** Phase 1A–1F suite is preserved. Both local final gate and remote final implementation CI measured **200 passed**. PostgreSQL FTS and pgvector execute real SQL. Native local PostgreSQL 17 and remote pgvector/PostgreSQL 16 are used; Redis/checkpoint verification is real, not SQLite substitution.

| Mandatory cases | Asserted behavior | Actual tests |
|---|---|---|
| 1–2 | Product A/B exclusion; unauthorized similarity=1.0 | `test_real_fts_vector_filter_before_ranking` |
| 3–4 | expired/superseded + historical snapshot | `test_historical_snapshot_retrieval_and_expired_fresh_exclusion` |
| 5–6 | duplicate deterministic merge and identical input | `test_phase1g_algorithms.py / test_query_embedding_uses_registry_and_real_pgvector` |
| 7–8 | allowed rerank/drop audit | `test_rerank_injection_is_audited_and_no_scope_extension` |
| 9–10 | language cannot broaden; tenant guessing | `test_search_snapshot_never_adds_new_index_and_languages_narrow / test_retrieval_api_dtos_auth_snapshot_and_scope_injection` |
| 11–12 | internal complete canonical provenance | `test_run_pack_sufficiency_idempotency_and_reproducibility` |
| 13–14 | external citation/hash/authority/snapshot | `test_verified_external_pin_reuse_not_active_and_citation_chain` |
| 15 | specific official sufficient | `test_sufficient_internal_does_not_download / specific official algorithm case` |
| 16–21 | generic/no authority/expired/topic/conflict/high-score sufficiency | `test_phase1g_algorithms.py parameterized cases` |
| 22–23 | augmentation trigger / avoid unnecessary fetch | `test_verified_external_pin_reuse_not_active_and_citation_chain / test_sufficient_internal_does_not_download` |
| 24–26 | untrusted/SSRF/private-IP/redirect/timeout/size/MIME | `test_phase1f_download_chunking.py (26 preserved cases) + external rejection cases` |
| 27–29 | official validation / no ACTIVE / snapshot pin | `test_verified_external_pin_reuse_not_active_and_citation_chain` |
| 30–33 | nonempty questions/actions, no fabricated laws/path | `test_phase1g_algorithms.py fallback assertions + empty PostgreSQL/API result cases` |
| 34–36 | Wiki DRAFT/review + inferred graph not legal | `test_wiki_draft_review_runtime_boundary / test_graph_provenance_review_and_bad_source_rollback` |
| Addendum 1–12 | automatic commit/outbox/build/READY/cache/retry/old snapshot | `12 tests in test_phase1g_publication_postgres.py` |
| Additional | FK pack rollback, optimistic concurrency, idempotency, redirect credentials | `test_pack_commit_fk_failure_rolls_back_without_parallel_result + policy/contract cases` |

## Actual Phase 1G test distribution

- `tests.test_phase1g_algorithms`: 16 PASS.
- `tests.test_phase1g_api_postgres`: 3 PASS.
- `tests.test_phase1g_external_postgres`: 9 PASS.
- `tests.test_phase1g_isolation_postgres`: 9 PASS.
- `tests.test_phase1g_navigation_postgres`: 2 PASS.
- `tests.test_phase1g_persistence_postgres`: 4 PASS.
- `tests.test_phase1g_publication_postgres`: 12 PASS.
- `tests.test_phase1g_search_postgres`: 3 PASS.

## Transaction / publication evidence

The publication addendum includes successful automatic READY materialization, duplicate and concurrent delivery, FTS/vector/cache failure and retry, previous READY and snapshot preservation, out-of-order handling, commit rollback and live background polling with no manual sync. The shared outbox emits no event/state on commit failure. Real citation FK failure rolls back an entire pack/item transaction.

Runtime checkpoint ownership, process restart/resume and duplicate resume remain **25/25**. B–F tenant/source-of-truth/registry/document/context regressions pass. Remote full log hash and artifacts are attributed to the remote CI, separately from the retained complete local log.

## Boundaries / exclusions / regression status

Phase 1E formal Context remains the only context input. Phase 1F PostgreSQL Source/Document/Version/Structure/Chunk/Binding/EvidenceReference/Citation tables remain canonical Knowledge Source of Truth. Retrieval stores, runtime materialization state, indexes, Wiki/Graph and RAGContextPack are derived. Runtime external evidence remains VERIFIED, separate from ACTIVE canonical knowledge.

Excluded: production model/provider execution, LLM answers, formal classification, regulation applicability, country-specific compliance routing, risk, Candidate/Final Compliance Path, required regulatory-document decisions and production legal agents. External parsing currently accepts attributed canonical JSON through the existing controlled MIME boundary; HTML/PDF web crawling and unrestricted discovery are outside this foundation. Embedding/rerank tests use explicit deterministic adapters behind ports. Original source text is preserved; no reviewed translation becomes original official text.

Phase 1A–1F regressions pass under the current 0007 migration. Earlier migration files 0001–0006 are unchanged. The historical Phase 1F main baseline remains `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95`; its 142-test baseline is historical and is not substituted for this Phase 1G 200-test result.

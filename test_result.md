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


---

# Phase 1H executed test results

Committed implementation full pytest: 284 passed in 55.41s; zero skipped, deselected, failed or errors. Phase 1H breakdown: AST 35, rules/classification 17, migration lineage 14, PostgreSQL governance/isolation 13, API 3, existing Phase 1G evidence integration 1, dual-path migration/downgrade 1 (84 total).

Schema regression: Phase 1B 16/16; 1C 20/20; 1D 15/15; 1E 22/22; 1F 29/29; 1G 58/58; 1H 20/20. Architecture 118/118. Existing separate-process checkpoint/start/interrupt/resume/retry smoke 25/25. Fresh and archived-baseline upgrade paths, schema equivalence and downgrade policy all pass.

Additional real HTTP smoke: Uvicorn on loopback; `/health/live`, `/health/ready`, `/health/dependencies` return 200/ok and unauthorized classification read returns 401. Authorized functional HTTP behavior is tested with actual FastAPI TestClient and PostgreSQL.

Local service versions: PostgreSQL 17.11 / pgvector 0.8.0 / Redis 8.0.2 / Python 3.12.14. Remote mandatory CI uses pgvector PostgreSQL 16 and Redis 7; its measured evidence is separate. Two observed nonfailure warnings remain: historical Starlette 422 constant deprecation and SQLAlchemy generic reflection not recognizing vector. Migration equivalence additionally queries PostgreSQL `format_type` including actual vector dimensions; no assertion is skipped or warning hidden.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.


# Phase1I — validation and attribution

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

The final-code mandatory gate includes Phase1I unit, PostgreSQL/API, locale and dual-path migration tests; all historical runtime tests are included. Required final results are recorded in evidence/phase1i/local/pytest_full_summary.json, all phase schema JSONs, architecture_rule_check.json, runtime_verify.json and the full ci_complete.log. Phase1I source tests use actual PostgreSQL, real existing context/knowledge/rule/governance services and Redis; inherited embedding fixtures inject deterministic adapters, not production provider execution.

The first complete353-case run passed at0347fc5702bac9639d66631878adf472b4ce5bd6 and remote CI37271852286 SUCCESS. The final code adds locale-neutral formal reason/config identifiers and durable prompt/template resource publication checks; it requires a new complete gate and exact-head remote run. Do not substitute the earlier run for final delivery proof. No skipped/deselected tests are accepted by the gate.

Expected unchanged historical gate assertions: B16, C20, D15, E22, F29, G58, H20; I24; architecture135; runtime25. Final observed counts and final remote conclusions are appended below after measurement. Remote job/API/artifact identity is kept separate from local logs; unavailable remote log bytes/hashes are never inferred.

## Phase1I final measured local gate

Code SHA `131d101cdd02999aa478c1a730f492c1729caf30`: **355 passed / 0 failed / 0 errors / 0 skipped / 0 deselected**, including **71 Phase1I tests** (43 pure domain/locale,27 real PostgreSQL/API,1 dual-path migration). I schema24/24, architecture135/135, runtime25/25; Phase1B–H schema regressions16/20/15/22/29/58/20 all PASS. Fresh and verified0008→0009 schema equivalence and downgrade roundtrip/refusal PASS.

The complete local log, XML, JSONs and SHA-256 manifest are in [evidence/phase1i/local](evidence/phase1i/local) and [local_manifest.json](evidence/phase1i/local_manifest.json). Local artifacts explicitly identify the frozen tested code SHA; subsequent documentation commits are separate. Final-head remote CI must pass before the entry decision and final delivery.

Final code revision `b2312e9ec48bd05e3398c23f79dcfcf1faf69b9f` adds one real PostgreSQL/API actor-visibility regression. Its new full gate must include356 tests (72 Phase1I); observed results will be recorded in evidence/phase1i/local-final. Earlier353/355 runs are preserved separately and do not substitute for final proof.

## Final scoped delivery gate — observed PASS

Code SHA `b2312e9ec48bd05e3398c23f79dcfcf1faf69b9f`: **356 passed / 0 failed / 0 errors / 0 skipped / 0 deselected**. This includes **72 Phase1I cases** (43 pure domain/locale,28 PostgreSQL/API,1 independent dual-path migration). Schema B–I16/20/15/22/29/58/20/24, architecture135/135 and runtime25/25 all PASS. Both migration paths/equivalence and empty/retained-data downgrade behavior PASS.

Final complete logs/XML/JSONs are in [evidence/phase1i/local-final](evidence/phase1i/local-final); bytes and hashes are recorded in [local_final_manifest.json](evidence/phase1i/local_final_manifest.json). Earlier evidence remains separately attributed. The remote gate must test the forthcoming exact documentation head including this source before entry issuance.

# Hybrid merge result

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

## Deterministic merge

`HybridMergeStrategy` deduplicates by canonical chunk ID and rejects inconsistent version/index identity for duplicate chunks. Duplicate occurrences in one channel cannot inflate the score. Policy selects weighted score or reciprocal rank fusion, lexical/vector weights, RRF constant, evidence threshold and candidate limit.

Weighted mode normalizes FTS scores with `score/(1+score)` and cosine score to [0,1]. RRF uses policy-weighted per-channel ranks. Stable tie ordering uses chunk ID. Independent lexical, vector, hybrid and optional rerank scores survive evidence assembly.

PASS: parameterized deterministic weighted/RRF tests, duplicate-channel tests, actual lexical+vector integration dedup and score assertions. The score does not determine official evidence authority, dates, jurisdiction coverage or sufficiency. No country/product/regulation code routing exists.

## Boundaries / exclusions / regression status

Phase 1E formal Context remains the only context input. Phase 1F PostgreSQL Source/Document/Version/Structure/Chunk/Binding/EvidenceReference/Citation tables remain canonical Knowledge Source of Truth. Retrieval stores, runtime materialization state, indexes, Wiki/Graph and RAGContextPack are derived. Runtime external evidence remains VERIFIED, separate from ACTIVE canonical knowledge.

Excluded: production model/provider execution, LLM answers, formal classification, regulation applicability, country-specific compliance routing, risk, Candidate/Final Compliance Path, required regulatory-document decisions and production legal agents. External parsing currently accepts attributed canonical JSON through the existing controlled MIME boundary; HTML/PDF web crawling and unrestricted discovery are outside this foundation. Embedding/rerank tests use explicit deterministic adapters behind ports. Original source text is preserved; no reviewed translation becomes original official text.

Phase 1A–1F regressions pass under the current 0007 migration. Earlier migration files 0001–0006 are unchanged. The historical Phase 1F main baseline remains `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95`; its 142-test baseline is historical and is not substituted for this Phase 1G 200-test result.

# Phase 1K-A executed test result

Phase: **Track B — Phase 1K-A foundation**, not full Phase 1K production integration.
Base: `f563e5067308e7eab6d3f89321b8b30da7c39044`; tag `v3.6-phase1g-pass`.
Tested implementation source SHA: `256b74df044870487d668764ffc0aa704806224e`; Run **37019990110**, Number **110**, Attempt **1**, **SUCCESS**.
Runner merge SHA: `64be7b05cf38aa8a8446dda95e0ed8402ee471aa`. Artifact **11231744443**, digest `sha256:e5390bf776f66cf50dc207c550dedad1f9f37cb6a3439c0fa54755c26f140c34`.
Full remote gate log: `ci_complete.log`, 74540 bytes, SHA-256 `131e01c87043cc4b3f4769c4fbcaff278815e5207309bfd2b12dd5178b8ab09f`.

Actual full PostgreSQL/runtime pytest: **276 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**. Local JUnit identifies **76 Track B tests** (64 non-PostgreSQL + 12 PostgreSQL) and all **200 frozen baseline tests**. The remote total is verified through official measured Check annotations; no remote JUnit ZIP download is claimed. The frozen test hashes plus full no-deselect gate preserve the same test set remotely.
Alembic remains **0007_phase1g**; **no migration**. Existing schema gates B/C/D/E/F/G: **16/16 / 20/20 / 15/15 / 22/22 / 29/29 / 58/58 PASS**. Frozen architecture checks **108/108**, additional Track B boundaries **20/20** (executed by full pytest), runtime/checkpoint ownership **25/25 PASS**. Phase 1A–1G regressions **PASS**.

Source of Truth: existing PostgreSQL Phase 1C model/provider/deployment/capability/health metadata, generic governed metadata versions, Prompt versions and AnalysisSnapshot registry pins. Registries remain projections; no duplicate authoritative store, publish mechanism, knowledge, parser, retrieval or workflow was introduced.

Known exclusions: full Phase 1K/1L compliance workflow, legal rules, formal classification/applicability/risk/path decisions, production agents, every provider SDK, multimodal binary ingestion, automatic health monitoring, production secret-vault/resource-source/audit/detection wiring, reversible mapping storage and next-phase development. Production callers must inject trusted scoped resource loading, approved detection when required, protected secret resolution and an available event audit sink; absent/failing mandatory dependencies block invocation. Tests inject deterministic adapters; PostgreSQL/Redis/pgvector remain real. No paid provider is required for CI.

Evidence: [implementation identity](evidence/phase1k-a/implementation-ci/verified_identity.json), [measured full gate](evidence/phase1k-a/implementation-ci/empirical_summary.json), [local full log](evidence/phase1k-a/local-final/ci_complete.log), [local JUnit](evidence/phase1k-a/local-final/pytest_full.xml), [Track B boundary results](evidence/phase1k-a/local-final/phase1k_a_boundary_check.json), [frozen hashes](evidence/phase1k-a/frozen_baseline_manifest.json).
The unchanged Phase 1G CI workflow/summary script is reused: its historical `phase: 1G` label identifies the gate script, while its pytest total includes the new Track B suite. These documents explicitly distinguish frozen Phase 1G 200-test baseline from the new 276-test foundation result. The later documentation-only publication head has its own final CI, recorded in the final PR description/receipt, never attributed to this earlier implementation SHA.

PASS: final local fresh PostgreSQL gate at implementation SHA `256b74df044870487d668764ffc0aa704806224e` and remote full mandatory CI independently execute **276 tests**, with no skip/deselect/failure/error. Real PostgreSQL/Redis/pgvector and LangGraph start/interrupt/restart/resume/retry are retained. Local JUnit programmatically counts the new cases:

| Test module | Passed cases |
|---|---:|
| `tests.test_phase1k_a_architecture` | 1 |
| `tests.test_phase1k_a_configuration_postgres` | 12 |
| `tests.test_phase1k_a_gateway` | 40 |
| `tests.test_phase1k_a_http_redaction` | 23 |

The unchanged baseline suite has 200 cases; new Track B has 76 (64 non-PostgreSQL and 12 real PostgreSQL). Legacy schema/architecture/runtime counts above remain separate from Track B boundary count. Deterministic fakes are only explicit tests. Frozen implementation hashes prove no weakened old assertions. `ruff check` passes for all new modules/tests/script; `git diff --check` passes. No migration or competing Alembic head.

Assertions cover all operations, capability/health/trust/residency, strict tenant/project intersection, internal-only/restricted/unknown-label denial, confidential redaction before external calls, failure/review/wrong-range masking blocks, approved fallback, no post-emission fallback, source preservation, prompt injection, raw secret/credential echo prevention, uniform nonexistent resources, authorization DTO rejection, structure/vector/rerank result validation, old-policy/model/prompt pins, new-publication isolation, revocation, effective dates, metadata rollback and governed prompt capability checks.

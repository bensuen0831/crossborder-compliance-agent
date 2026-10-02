# External evidence augmentation result

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

## Trigger / trust / controlled transport

Only PARTIALLY_SUFFICIENT or INSUFFICIENT plus a pinned enabled retrieval/trusted policy triggers augmentation. SUFFICIENT avoids unnecessary fetch; CONFLICTED remains unresolved with guidance. The deterministic query planner/discovery ports never confer authority. Approved policy rules and canonical source URLs supply authority/tier/jurisdiction/permission/product eligibility.

The existing ControlledDownloaderPort/ControlledHTTPSDownloader enforces HTTPS, approved host, validated DNS/global IPs pinned per redirect, private-IP/SSRF rejection, timeout, size, MIME, content encoding/truncation and request audit. The compatible audit extension returns final canonical URL, which must match the registered URL or credential-free approved redirect exactly.

Attributed canonical JSON is parsed/validated for authority, approved jurisdictions, language, publication/effective/expiry dates, node locator/text, metadata topic/reg refs, source/content hashes and citation provenance. T1/T2 must match official source types. T3 is supporting; T4 and LLM-only discovery never become evidence. Original bytes are bounded and retained in the derived runtime record.

## Snapshot / ACTIVE boundary

External runtime records are VERIFIED with `active_knowledge=false`, never inserted as canonical Documents/Versions or ACTIVE knowledge. The snapshot pins the runtime record and policy identities; its parsed artifact/hash/URL/retrieval date are frozen. Later requests on the same snapshot reuse it without fetching website updates. Permission/source revocation can only remove it from the response.

PASS: 9 PostgreSQL external cases verify attribution/hash/date/permission/T4/timeout/structure failures, successful pin/citation/hash reuse and no ACTIVE write; 26 preserved Phase 1F downloader/chunking cases include SSRF, untrusted host, redirects, MIME, size, truncation and deadline. The 4 new redirect contract cases prohibit URL credentials from escaping through policy/evidence DTOs.

## Boundaries / exclusions / regression status

Phase 1E formal Context remains the only context input. Phase 1F PostgreSQL Source/Document/Version/Structure/Chunk/Binding/EvidenceReference/Citation tables remain canonical Knowledge Source of Truth. Retrieval stores, runtime materialization state, indexes, Wiki/Graph and RAGContextPack are derived. Runtime external evidence remains VERIFIED, separate from ACTIVE canonical knowledge.

Excluded: production model/provider execution, LLM answers, formal classification, regulation applicability, country-specific compliance routing, risk, Candidate/Final Compliance Path, required regulatory-document decisions and production legal agents. External parsing currently accepts attributed canonical JSON through the existing controlled MIME boundary; HTML/PDF web crawling and unrestricted discovery are outside this foundation. Embedding/rerank tests use explicit deterministic adapters behind ports. Original source text is preserved; no reviewed translation becomes original official text.

Phase 1A–1F regressions pass under the current 0007 migration. Earlier migration files 0001–0006 are unchanged. The historical Phase 1F main baseline remains `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95`; its 142-test baseline is historical and is not substituted for this Phase 1G 200-test result.

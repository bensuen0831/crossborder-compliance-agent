# Retrieval API result

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

## Actual routes / DTO contracts

| Method | Route | Actual contract / boundary |
|---|---|---|
| POST | `/api/v1/projects/{project_id}/knowledge/retrieve` | RetrievalRequestDTO → RetrievalResponseDTO; server resolves scope |
| GET | `/api/v1/retrieval-runs/{id}` | owner + tenant + current scope revalidation |
| GET | `/api/v1/evidence-packs/{id}` | typed EvidencePack, scoped response projection |
| GET | `/api/v1/knowledge-sufficiency/{id}` | typed current permitted KnowledgeSufficiencyResult |
| POST | `/api/v1/admin/knowledge-retrieval-policies` | typed policy envelope; validated frozen parameters |
| POST | `/api/v1/admin/knowledge-sufficiency-policies` | versioned sufficiency policy |
| POST | `/api/v1/admin/trusted-source-policies` | versioned approved source rules |
| GET | `/api/v1/admin/{policy-kind}/{id}` | actual version DTO; admin/tenant guard |
| POST | `/api/v1/admin/{policy-kind}/versions/{id}/publish` | expected record version; ACTIVE transition |
| POST | `/api/v1/admin/wiki` | approved source IDs → DRAFT navigation DTO |
| POST | `/api/v1/admin/wiki/{id}/{validate\|submit-review\|approve\|publish}` | durable review/expected version |
| GET | `/api/v1/projects/{project_id}/wiki/{page_id}` | snapshot-required ACTIVE allowed source versions |
| POST | `/api/v1/admin/knowledge-graph/{node\|edge}` | validated source-chain DRAFT |
| POST | `/api/v1/admin/knowledge-graph/{kind}/{id}/{submit-review\|approve}` | independent review/expected version |
| GET | `/api/v1/admin/knowledge-versions/{id}/runtime-readiness` | typed publication readiness; admin guard |

`policy-kind` is one of the three explicit policy resource codes above. Ingestion/governance routes from Phase 1F remain intact. Its successful Publish atomically schedules background runtime synchronization; the API does not require a manual refresh endpoint.

401 requires trusted RepositoryContext; 403 protects actor/admin permissions; 404 fails closed for tenant UUID guessing/missing objects; 409 handles stale/idempotency conflicts; 422 rejects malformed scope/DTO/lifecycle inputs. No ORM objects or provider credentials are returned. There is no optional manual augment endpoint because controlled augmentation is already part of the policy-driven run.

PASS: all 3 API PostgreSQL tests verify actual registered routes, request scope-injection rejection, result/evidence/sufficiency/readiness DTOs, auth/tenant/actor guards, admin policy publication and Wiki route precedence.

## Boundaries / exclusions / regression status

Phase 1E formal Context remains the only context input. Phase 1F PostgreSQL Source/Document/Version/Structure/Chunk/Binding/EvidenceReference/Citation tables remain canonical Knowledge Source of Truth. Retrieval stores, runtime materialization state, indexes, Wiki/Graph and RAGContextPack are derived. Runtime external evidence remains VERIFIED, separate from ACTIVE canonical knowledge.

Excluded: production model/provider execution, LLM answers, formal classification, regulation applicability, country-specific compliance routing, risk, Candidate/Final Compliance Path, required regulatory-document decisions and production legal agents. External parsing currently accepts attributed canonical JSON through the existing controlled MIME boundary; HTML/PDF web crawling and unrestricted discovery are outside this foundation. Embedding/rerank tests use explicit deterministic adapters behind ports. Original source text is preserved; no reviewed translation becomes original official text.

Phase 1A–1F regressions pass under the current 0007 migration. Earlier migration files 0001–0006 are unchanged. The historical Phase 1F main baseline remains `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95`; its 142-test baseline is historical and is not substituted for this Phase 1G 200-test result.

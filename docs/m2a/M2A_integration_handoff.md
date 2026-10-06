# M2-A implementation checkpoint — BLOCKED

Verified base:83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1; annotated v3.6-m1-phase1lb-pass; single Alembic0010_phase1j. Dedicated milestone-m2a-production-intake worktree; existing worktrees preserved.

The partial implementation reuses Project, ProjectVersion.intake_json and ProjectIntakeContext; no new intake/project/snapshot store or migration. API accepts canonical writable facts only, server constructs provenance/identities. Saves append versions, preserve historical payloads and reject stale versions. Confirmation prepares the existing context/scope/config pins and a stable canonical workflow run within one PostgreSQL transaction; failure rolls back. Existing H5/root/router/transport/generated contracts are reused. The frontend production flow and complete closure are not certified.

## Proven frozen-contract blocker

Actual fresh-project confirmation creates one snapshot and START/READ preserve project/snapshot/run identity, but canonical workflow returns FAILED at applicability. That project has zero formal BusinessFacts. Phase1L-B's scenario_rule_hits requires validated scenario and independent formal business facts; it correctly does not treat an intake description as a fabricated legal fact. The existing BusinessFact candidate ingestion is document-parse-bound, and SourceTraceRef.document_version_id and BusinessFactCandidate.parse_run_id are NOT NULL. ProjectIntakeContext provenance can audit the intake but does not supply an approved Candidate → Validation → Formal BusinessFact conversion contract.

HIGH_REASONING_ESCALATION_REQUIRED. High review must settle the canonical USER_INPUT candidate/provenance preparation contract and the typed INSUFFICIENT_INPUT boundary for missing scenario facts. Do not bypass validation, invent document/parse IDs, write authoritative facts directly, or alter legal decisions. No speculative redesign was implemented.

Measured evidence: evidence/m2a/blocker_evidence.json. Focused PostgreSQL: four lifecycle/security/idempotency tests passed before the START counterexample; atomic rollback separately passed. Existing M1 focused frontend23 PASS; typecheck PASS. Existing Architecture151/151 PASS. New M2-A architecture checks, production browser UAT, full regression/runtime, exact-head CI, Draft PR and final delivery remain unperformed. Earlier failed environment checks were diagnosed; actual dedicated PostgreSQL now runs at0010.

No M2-A PASS. Do not create M2B_entry_decision.md or start M2-B/C/D/K-B; no merge. Resume only after High resolves this blocking contract; retain all current work and ancestry. Other unfinished work includes field/document/reference validation, full input bounds, current permission handling, backend host reconstruction alongside existing hosts, and complete frontend dirty/retry/idempotency coverage. Historical ownership gates need a finite M2-A reviewed-source allowance before closure; they must not be weakened.

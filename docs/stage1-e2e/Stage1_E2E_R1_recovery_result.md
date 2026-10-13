# STAGE1-E2E-R1 recovery result

`HIGH_REASONING_ESCALATION_REQUIRED`

`STAGE1-E2E-R1 = BLOCKED`

`PROPOSED MIGRATION = 0019_stage1_candidate_governance`

`STAGE1 FULL E2E RESUME = BLOCKED`

`STAGE1 FULL E2E PR CLOSURE = BLOCKED`

`MAIN INTEGRATION = PENDING`

`Paid Internet LLM = NOT EXECUTED`

`Stage 2 = NOT STARTED`

## Completed evidence

Baseline HEAD, refreshed origin/main and annotated v3.7-m2e-pass target all match `df3a10923734495d728981f4f319b66afadf8c71`. Alembic and the real diagnostic PostgreSQL database remain at `0018_phase1h_multijurisdiction_classification_identity`.

The retained original real HTTP/DOCX/local-HTTP LLM counterexample shows a newly generated candidate became a VALIDATED formal fact under POLICY during confirmation, without intervening user authorization. This turn inspected the relevant owning adapters and real database constraints, exercised the candidate-resolution immutability guard and checked the existing Snapshot-only LLM request contract.

Measured D0 checks:

| Check | Measured result |
| --- | --- |
| Baseline / tag / migration identity | PASS |
| Existing candidate-resolution rewrite to pre-confirm authorization | Rejected: IMMUTABLE_CANDIDATE_RESOLUTION_REWRITE |
| Existing resolution row before/after probe | Same SHA-256; no change |
| LLMRequest without Snapshot identity | Rejected: analysis_snapshot_id missing |
| Audit insertion with genuinely absent run/Snapshot IDs | Rejected: SQLSTATE 23502, workflow_run_id; transaction rolled back |
| Existing external pre-snapshot audit convention | Source confirmed: empty-string unbound identities; not a new HTTP acceptance run |
| Historical production source/migrations | Preserved; see machine-readable source digests |

## Exact blocker

`PRECONFIRM_AUTHORIZATION_PERSISTENCE_IDENTITY_MISSING`

There is no current owning record for an immutable draft-wide candidate preparation and independently append-only user decisions that survives later formal mapping. The current intake update creates a new ProjectVersion, invalidating authorization bound to the old version; in-place JSON mutation would change the documented immutable-payload contract. CandidateResolution has a formal/context-version unique identity and rejects later mapping rewrites. BusinessFactResolution is a formal mapping. Completed parse provenance belongs to extraction, not project consent.

The existing canonical audit table already supports external pre-snapshot operation logs through empty strings. This finding is retained and prevents the incorrect claim that NOT NULL alone proves migration necessity. It does not supply the preparation/decision operational identities. Using audit JSON as the new authoritative business event store, or a mutable intake annex, would require an explicit ownership redesign. Neither is silently adopted as a no-migration workaround.

The compatible proposal adds only preparation/decision owning storage and a reviewed extension of the existing typed gateway/audit scope. It does not duplicate candidate/formal authority, registry, workflow, checkpointer, legal engine or M2-D ReviewTask. See the inventory for all ten persistence questions and the design for columns/indexes, scope constraints, legacy audit compatibility and downgrade refusal.

## Not executed

No R1 migration, production implementation, new candidate routes/UI, focused recovery acceptance, full regression, Browser recovery, new CI, PR, merge or tag. Historical counts Backend910 / Architecture307 / Runtime25 / Frontend135 / Browser60 are baseline references only. This result does not claim R1 PASS or four-outcome Stage1 acceptance.

D0 schema diagnostics ran on PostgreSQL17.11; formal baseline CI used its own recorded environment. The schema probe and guard checks do not replace fresh/upgrade migration equivalence or functional acceptance. Paid Internet providers were not called. No browser retry claim is made for unexecuted recovery Browser tests.

## Approval boundary

The user explicitly states in R1 sections 35–36 and 81 that 0019 is not approved, and requires stopping after D0 when compatible persistence is missing. Work therefore stops with a concrete architecture proposal before implementation or PR closure. Architecture approval must choose the proposed `0019_stage1_candidate_governance` scope or explicitly approve an alternative ownership design; recovery cannot resume by implicitly mutating frozen intake or resolution semantics.

Artifacts:

- `Stage1_E2E_R1_candidate_contract_inventory.md`
- `Stage1_E2E_R1_candidate_governance_design.md`
- `evidence/stage1-full-e2e/r1_candidate_governance.json`
- `evidence/stage1-full-e2e/r1_schema_inventory.json`

Existing D0 counterexample/report files are preserved; no new main/evidence commit has been created.

# M2-E contract blocker — implementation stopped

HIGH_REASONING_ESCALATION_REQUIRED — M2-E = BLOCKED.

## Exact counterexample

Baseline `0f5a40c5ca3a8771624fb38e9380856d79e67342`, tag `v3.7-phase1kb-pass`. The real PostgreSQL/HTTP vertical slice creates an integration identity and a new project, supplies distinct canonical source/destination jurisdictions, uploads a genuine DOCX and completes the existing parser. Both jurisdictions have genuinely published knowledge/legal basis and applicability configuration. A published classification Scheme and Rule cover both jurisdictions through the existing review/publish owners.

`POST /api/v1/external/projects/{project_id}/intake/confirm` returns `422 INVALID_INPUT`. The canonical owning exception is `classification requires one resolved scheme jurisdiction`. The acceptance test remains failing; it is not skipped, deleted or replaced by a precomputed result.

Reproduction (local PostgreSQL and existing fixtures required):

```bash
source artifacts/m2e/environment.sh
/workspace/.onboarding/phase1i-venv/bin/python -m pytest -q tests/test_m2e_vertical_postgres.py -x
```

Measured diagnostic execution: **1 failed in 5.48s**. The diagnostic printer used during investigation has been removed; the public API continues returning a sanitized error.

## Affected authority

- `infrastructure/persistence/rule_governance.py:110`: a published rule's jurisdictions must be covered by its classification Scheme.
- `infrastructure/persistence/classification_repository.py:149`: Scheme jurisdictions intersecting the pinned validated context must resolve to **exactly one** jurisdiction. A Scheme covering both source and destination fails here.
- `infrastructure/intake_composition.py:145`: production confirmation requires **exactly one ACTIVE Scheme**. Separate source/destination Schemes are rejected here.
- `application/workflow_formal.py:349`: canonical jurisdiction routing requires the plan's applicability bindings to cover the validated context jurisdictions. Omitting a jurisdiction is a WARNING, not ordinary success.
- `domain/compliance_profiles.py:186`: applicability requires a nonempty governed Rule set; omitting rules is not a compliant repair.

These existing checks were preserved. No country branches, alternate workflow, fabricated Evidence, rewritten legal owner or external-specific legal interpretation was introduced to bypass them.

## Minimum compliant options requiring owning-contract review

1. Phase1H / M2-A approve and implement explicit jurisdiction-scoped configuration initialization and exact immutable Rule/Scheme pins for a multi-jurisdiction Snapshot; retain existing single-jurisdiction behavior and prove Phase1H/I/J, temporal and review regressions. Canonical orchestration must consume those pins without inferred or latest fallback. This is a prerequisite correction owned by those contracts, not an external-channel legal implementation.
2. Keep the existing contracts and record multi-jurisdiction production intake as unsupported. This preserves fail-closed behavior but **cannot satisfy the required M2-E vertical slice**, so M2-E remains BLOCKED.

Choosing an arbitrary first jurisdiction, dropping the destination binding, mapping a WARNING to COMPLETED or treating ungoverned empty rule sets as legal success is not acceptable.

## Work retained / measured limits

D0 inventory and exact baseline/tag start gate passed. WIP includes northbound identities with scrypt hashes, revocable OAuth/service credentials, project bindings, central scope mapping, a canonical-service façade, technical async delivery, compact SSE/WS contracts, encrypted-reference webhooks and actual HTTP signature/retry tests. None is represented as completed production closure.

Prior focused executions: identity PostgreSQL **10 PASS**, HTTP façade **8 PASS**, webhook PostgreSQL/actual callback **10 PASS**. These are WIP measurements, not current exact-head closure or a full regression count. The technical checkpointer initialization concurrency fix is preserved as WIP and needs a focused parallel/recovery regression before acceptance.

Local migration `0017_m2e_external_agent_api` is a single successor to0016. Fresh development upgrade and empty downgrade/re-upgrade succeeded. Exact0016 dual-path equivalence and populated downgrade-refusal tests remain pending. Frozen0001–0016 byte hashes are recorded unchanged in `evidence/m2e/blocked_checkpoint.json`.

Admin UI, external-only OpenAPI/SDK, dedicated M2-E CI, additive architecture checks, full regression, browser and exact-head closure are not completed. Existing baseline counts844/269/25/130/57 are historical baseline evidence only and have not been reasserted for this WIP. No frontend files changed. No paid Internet LLM acceptance executed.

No merge, main advancement, tag, next-phase entry or Full Stage1 E2E was performed. Stage2 remains NOT STARTED.

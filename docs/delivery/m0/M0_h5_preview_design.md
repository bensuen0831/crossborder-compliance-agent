# M0 Knowledge & Evidence Preview — Track C

Base: `f563e5067308e7eab6d3f89321b8b30da7c39044`, tag `v3.6-phase1g-pass`.
Branch/worktree: `milestone-m0-h5-preview`, `/workspace/crossborder-m0-h5-preview`.
Draft PR: https://github.com/bensuen0831/crossborder-compliance-agent/pull/11.

M0 exposes the existing Phase 1G Knowledge Retrieval, EvidencePack, KnowledgeSufficiencyResult,
fallback guidance and runtime materialization APIs. React renders backend results; it performs
no legal decision, retrieval, permission resolution or publication. Phase 1A–1G and migrations
0001–0007 remain byte-for-byte unchanged. No new Alembic revision exists.

Start Gate was executed: origin/main, peeled tag and initial HEAD matched the exact base;
reflog confirms branch creation from that commit; worktree was clean; architecture 108/108
passed. The early checkpoint `52c130622460e0c7957fe1eae32c2c2ff955a9b6` was pushed and PR #11
created as a draft. No other agent was observed sharing the worktree. Repository architecture,
Phase 1B/E/F/G contracts and Phase 1H entry governance were read. There was no separate Master
Specification or frontend workspace in the baseline. The user-supplied Track C specification
provides the M0 scope.

## User flow

Trusted session → choose authorized project/snapshot → inspect backend-pinned context → submit
query → inspect evidence cards/table → open source/citation drawer → read sufficiency and
typed fallback → inspect authorized runtime readiness. A no-match result preserves actionable
fallback rather than manufacturing a compliance answer. Unfinished Stage 1 navigation is disabled.

The Midnight theme is centralized in Ant Design theme tokens. React Router provides stable
`/knowledge` and `/runtime` routes. Business product/scenario/jurisdiction labels come from
Metadata Registry APIs. Technical backend codes are retained; known guidance codes have
presentation translations, without inventing obligations or changing backend meaning.

## Integration gaps and deliberate limits

The baseline has no session API or list of authorized projects/snapshots/policies. Production
deployments must supply the presentation-only `/api/v1/session` and `/api/v1/logout` contract
defined in `frontend/src/api/contracts.ts`. M0 defaults to those routes and shows an explicit
integration-unavailable state rather than inventing an authenticated user. A separate loopback
UAT adapter implements `/m0-demo/session`, login and logout for synthetic personas only.

Product/Scenario/Jurisdiction are snapshot-pinned: M0 displays read-only selectors, not a client
scope override. Choosing another authorized context changes the project/snapshot bundle. Editing
formal context belongs to its existing backend workflow, not an M0 search filter. There is no
Product Domain listing endpoint; backend-approved domain IDs are displayed without invented
labels. Session org/department labels remain absent when the trusted identity does not supply them.

EvidencePackItem has no document title or per-item product/scenario dimension list. Its canonical
locator is the heading; source, provenance and backend-resolved request scope remain visible.
M0 does not fan out to Admin content endpoints to fill gaps. Runtime readiness is an existing
`knowledge:admin` route; ordinary users do not issue it. No full Admin forms are implemented.

## Reuse First classification

| Component | Classification | Why |
|---|---|---|
| Phase 1G APIs, typed results, Scope Resolver, security | REUSE | Frozen implemented capabilities remain authoritative |
| OpenAPI export and generated TypeScript | EXTEND | Consumer artifact from existing exact schemas, no new domain DTO |
| React, Vite, TypeScript, Router, TanStack Query, Ant Design, i18next, Ajv | ADD_DEPENDENCY | Mature frontend infrastructure; basic controls are library components |
| AppShell, ContextSelector, evidence/sufficiency composition | EXTEND | Presentation of existing backend contracts |
| Local UAT identity/session adapter | CUSTOM_BUILD | Baseline lacks HTTP identity wiring; isolated synthetic test adapter only |
| UAT seeding and publication | REUSE | Existing Phase 1F/G fixtures, review, publication, resolver and policies |

Zustand is unnecessary for M0: TanStack Query owns server state and component state owns selection.
No second Registry, Knowledge platform, Workflow runtime, parser, index, Source of Truth or
tenant/security resolver is created. This milestone does not complete Phase 1M.

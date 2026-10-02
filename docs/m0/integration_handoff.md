# INTEGRATION HANDOFF

1. Task / Track: C — M0 Knowledge & Evidence Preview; reusable later Phase 1M foundation.
2. Branch: milestone-m0-h5-preview.
3. Base SHA: f563e5067308e7eab6d3f89321b8b30da7c39044; v3.6-phase1g-pass.
4. Final tested SHA: pending final pushed implementation CI; exact identity will be recorded after verification.
5. PR: #11, https://github.com/bensuen0831/crossborder-compliance-agent/pull/11; DRAFT, target main, no merge.
6. New files: frontend/, scripts/m0_preview/, docs/m0/, evidence/m0/, tests/test_m0_preview_security.py, .github/workflows/m0-h5-preview.yml.
7. Modified files: only newly introduced Track C files since checkpoint; original frozen files unchanged.
8. Migration changes: NONE; head stays 0007_phase1g. No competing 0008.
9. API / DTO changes: no frozen backend changes; generated consumer types; separate presentation-session integration contract and local UAT-only routes.
10. Config / Registry changes: frontend theme/i18n/Vite configuration only; no new business registry. UAT uses existing policies and outbox publication.
11. Dependencies added: frontend React, TypeScript, Vite, Router, TanStack Query, Ant Design, i18next, Ajv and dev test/lint/type tooling; no backend additions, no unnecessary Zustand.
12. Architecture Rules added/modified: NONE; all 133 existing rules preserved, 108 executable checks PASS.
13. Tests added: 20 frontend component/unit/contract tests, 3 real browser UAT flows, 5 backend UAT security tests.
14. Local test results: typecheck/lint/build PASS; original+new Python suite 205 PASS, schema 58/58, architecture 108/108, runtime 25/25; frontend 20 PASS, browser 3 PASS; final remote result pending.
15. Remote CI result: pending final pushed implementation; do not infer remote PASS from local results.
16. Interfaces consumed: metadata, KnowledgeScope, RetrievalResponseDTO/RAGContextPack, EvidencePackItem, KnowledgeSufficiencyResult, typed fallback, Admin runtime readiness, trusted RepositoryContext.
17. Interfaces provided: reusable M0 components, /knowledge and /runtime routes; centralized typed API client; production session/logout contract; explicitly loopback synthetic UAT adapter.
18. Known integration risks: production session/project/snapshot/policy listing is not in baseline; Product Domain/title/per-item dimension gaps remain documented; org/department unavailable in fixture; readiness is admin-only; lexical UAT does not claim real model/vector provider; initial enterprise JS footprint can be optimized later.
19. Required merge order: integrates directly with frozen Phase 1G; no dependency on Phase 1H/0008 or Track D CRUD; coordinate frontend route ownership with Track D/Phase 1M before their later integration. Never merge automatically.
20. Required post-merge tests: M0 frontend quality workflow, real-backend browser UAT, full unchanged smoke/run_gate.sh regressions on fresh DB, tenant/permission isolation, regeneration zero diff and production build with demo disabled.
21. Demo/UAT: A authorized query → real PostgreSQL FTS evidence → citation drawer → insufficiency/fallback → READY; B isolation/404; no-match actionable guidance; see M0_demo_runbook.md.
22. PASS / BLOCKED: local acceptance verified; final remote acceptance pending. Do not declare Phase 1M complete. Stop after M0.

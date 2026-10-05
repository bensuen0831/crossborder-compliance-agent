# INTEGRATION HANDOFF

1. Task / Track: C — M0 Knowledge & Evidence Preview; reusable later Phase 1M foundation.
2. Branch: milestone-m0-h5-preview.
3. Base SHA: f563e5067308e7eab6d3f89321b8b30da7c39044; v3.6-phase1g-pass.
4. Tested implementation SHA: 90b4ac5b06f0e12e95a559e7c7354f409d292b4e; both independent GitHub workflows succeeded on this exact head. Subsequent evidence/documentation-only commits are identified and validated by their own PR head checks; use the current tested PR head when integrating.
5. PR: #11, https://github.com/bensuen0831/crossborder-compliance-agent/pull/11; DRAFT, target main, no merge.
6. New files: frontend/, scripts/m0_preview/, docs/m0/, evidence/m0/, tests/test_m0_preview_security.py, .github/workflows/m0-h5-preview.yml.
7. Modified files: only newly introduced Track C files since checkpoint; original frozen files unchanged.
8. Migration changes: NONE; head stays 0007_phase1g. No competing 0008.
9. API / DTO changes: no frozen backend changes; generated consumer types; separate presentation-session integration contract and local UAT-only routes.
10. Config / Registry changes: frontend theme/i18n/Vite configuration only; no new business registry. UAT uses existing policies and outbox publication.
11. Dependencies added: frontend React, TypeScript, Vite, Router, TanStack Query, Ant Design, i18next, Ajv and dev test/lint/type tooling; no backend additions, no unnecessary Zustand.
12. Architecture Rules added/modified: NONE; all 133 existing rules preserved, 108 executable checks PASS.
13. Tests added: 20 frontend component/unit/contract tests, 3 real browser UAT flows, 5 backend UAT security tests.
14. Local test results: typecheck/lint/build PASS; original+new Python suite 205 PASS, schema 58/58, architecture 108/108, runtime 25/25; frontend 20 PASS, browser 3 PASS. Measured working-tree hashes are in evidence/m0/local-validation.json.
15. Remote CI result: PASS on implementation SHA 90b4ac5b06f0e12e95a559e7c7354f409d292b4e. M0 workflow run 37019134461: frontend and real-backend-uat jobs, all steps success. Original regression run 37019134460: contract-tests and mandatory-runtime-smoke jobs, all steps success. GitHub REST run/job/artifact metadata and server-reported digests are recorded in evidence/m0/remote-ci.json. Full remote logs/artifact archives could not be downloaded because their redirect hosts remain blocked; their contents and digests have not been independently recomputed locally.
16. Interfaces consumed: metadata, KnowledgeScope, RetrievalResponseDTO/RAGContextPack, EvidencePackItem, KnowledgeSufficiencyResult, typed fallback, Admin runtime readiness, trusted RepositoryContext.
17. Interfaces provided: reusable M0 components, /knowledge and /runtime routes; centralized typed API client; production session/logout contract; explicitly loopback synthetic UAT adapter.
18. Known integration risks: production session/project/snapshot/policy listing is not in baseline; Product Domain/title/per-item dimension gaps remain documented; org/department unavailable in fixture; readiness is admin-only; lexical UAT does not claim real model/vector provider; initial enterprise JS footprint can be optimized later. CI log/artifact redirect hosts were added to a saved environment configuration draft; Review/Save/Publish is needed to activate them. This does not block the observed successful CI jobs or the executed local UAT.
19. Required merge order: integrates directly with frozen Phase 1G; no dependency on Phase 1H/0008 or Track D CRUD; coordinate frontend route ownership with Track D/Phase 1M before their later integration. Never merge automatically.
20. Required post-merge tests: M0 frontend quality workflow, real-backend browser UAT, full unchanged smoke/run_gate.sh regressions on fresh DB, tenant/permission isolation, regeneration zero diff and production build with demo disabled.
21. Demo/UAT: A authorized query → real PostgreSQL FTS evidence → citation drawer → insufficiency/fallback → READY; B isolation/404; no-match actionable guidance; see M0_demo_runbook.md.
22. PASS / BLOCKED: M0 KNOWLEDGE & EVIDENCE PREVIEW = PASS. Real local acceptance and exact-implementation remote CI are verified. Keep PR #11 DRAFT; do not merge. Phase 1M is not complete. Stop after M0.

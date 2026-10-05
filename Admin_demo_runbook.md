# Integrated Admin demo runbook

Use the ONE canonical frontend, not the removed standalone frontend/admin application. Follow the backend/seed/Vite commands in stage1_alpha_integration_handoff.md. The loopback demo requires explicit M0_LOCAL_UAT=1 and VITE_M0_DEMO=true; it supplies synthetic sessions only.

1. Sign in A and select the seeded authorized context.
2. Query Generic in Knowledge, inspect Evidence/Citation and Sufficiency/Fallback, and verify READY.
3. Open Admin in the same shell; choose Knowledge operations and open the returned evidence knowledge_version_id. Inspect the ACTIVE version, scope bindings and actual backend runtime readiness.
4. Open Rules; use a known Rule version ID to inspect the existing Phase 1H contract and validate persisted DRAFT tests when authorized. Rule authoring is explicitly unavailable in this screen.
5. Switch to the normal PROJECT persona. Admin state is cleared and access is unavailable; direct approve/publish/archive calls return 403. Recovery is absent (404), not a success placeholder.
6. Run the LLM security regression to show restricted-context external routing denial, before provider invocation. Deterministic test adapters require no external keys and send no restricted data to a real external model.

Production login/contextual RBAC/ingestion deployment remain upstream gaps. Imports are disabled without trusted deployment capability. The original isolated D demo instructions remain under docs/delivery/admin-foundation/Admin_demo_runbook.md.

# M1 integration handoff

Branch milestone-m1-intake-analysis-alpha, exact base f1353372a1d8894535dc71765e3cd62597619fd5. One canonical H5 host and unchanged production dependencies/lock. Frontend, M1 docs/evidence and frontend-specific CI only; no src/alembic/architecture/backend changes.

Reproduce: npm ci --prefix frontend; typecheck/lint/test/check:i18n/build. Export models using frontend/scripts/m1/export_contracts.py then existing openapi-typescript; verify generated files unchanged. For real UAT use PostgreSQL/Redis, alembic upgrade head (0010), M0_LOCAL_UAT=1, seed a fresh manifest via frontend/scripts/m1/uat.py --seed, start its loopback adapter and canonical Vite with VITE_M0_DEMO=true/VITE_SESSION_PATH=/m0-demo/session, set M1_UAT_MANIFEST and run m1.spec.ts with zero retries.

Fixtures reuse existing Phase1E/F/G/H/I governed services and persistence. No fake Classification/Applicability result is returned. Existing M0 CI explicitly selects its own knowledge.spec.ts fixture family; M1 CI exercises M1 separately against exact PR head.

Review Draft only; do not merge or start M2. Later verified Phase1L-B closure can bind the intake to its authorized workflow contract; preserve this draft/read boundary until then. Task checkpoint is artifacts/m1/phase_progress_checkpoint.md, never the root checkpoint.

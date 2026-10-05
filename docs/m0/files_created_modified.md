# Track C file inventory

All milestone documents are under docs/m0 to avoid overwriting the frozen root delivery files.

New ownership roots: frontend/, scripts/m0_preview/, docs/m0/, evidence/m0/.
Additional Track C files: tests/test_m0_preview_security.py and
.github/workflows/m0-h5-preview.yml. The test is additive; existing tests are unchanged.
Evidence includes a synthetic UAT screenshot, measured local-validation.json and exact-head
GitHub run/job/artifact metadata plus empirical check annotations in remote-ci.json. Verification
history preserves the earlier failed browser step and the later nine passing independent
executions. Metadata distinguishes blocked downloads from inspected output and does not claim
local verification of remote archive digests.

Frontend contains package.json/lockfile, Vite/TS/ESLint/Playwright settings, AppShell/routes,
central theme/i18n/layout, exact exported OpenAPI/generated types, centralized client/contracts,
query hooks/mappers, ContextSelector, QueryPanel, EvidenceCard/Table/CitationDrawer,
Sufficiency/Fallback, RuntimeStatus/Health, common states/FeatureGate, test setup and synthetic
HTTP fixtures, component/contract tests and three browser flows.

scripts/m0_preview contains export_contracts.py, seed.py and server.py. These consume existing
Phase 1F/G fixtures/routers/services and never add canonical storage or migrations.

Changes after the early WIP checkpoint refine only those new Track C files. No existing src/**,
alembic/**, tests/** (other than the new M0 file), ARCHITECTURE_RULES.md, pyproject.toml, root
delivery document or original CI workflow is modified. Exact inventory is the PR's Files changed
and `git diff --name-status f563e5067308e7eab6d3f89321b8b30da7c39044 HEAD`.

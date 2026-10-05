# Stage1-alpha integration test result

**Local integrated gates: PASS.** Remote exact-head CI is reported in the Draft PR/final checkpoint; local evidence does not claim an unrun remote result.

| Gate | Result |
|---|---|
| Track B full Python / architecture / LLM boundaries | 360 / 118 / 20 PASS |
| Track C full Python / unit / real browser | 365 / 20 / 9 PASS |
| Track D focused backend before consolidation | 2 PASS |
| Final full Python, including runtime and new security/Rule adapter regression | 370 PASS, zero skipped, failed or errors |
| Phase 1B–1H schema and fresh multi-process runtime start/resume/retry proof | PASS |
| Architecture Rules 1–139 | 118/118 executable checks PASS |
| LLM security/boundary checks | 20/20 PASS |
| Single-host/source-ancestry/evidence/dependency integrity | 13/13 PASS |
| npm ci, lock integrity, frozen API/type regeneration | PASS, C declared dependencies/lock/generated API unchanged; package scripts add mandatory i18n policy |
| Typecheck / canonical lint / production build | PASS |
| Final frontend unit | 63 PASS |
| Real PostgreSQL/Redis/Chromium browser UAT | 36 PASS, three locales × four scenarios × three independent executions, zero retries |
| M0/session/Admin/Rule API security | 8 PASS (included in full Python count) |
| Alembic head / migration diff against approved H | 0008_phase1h / no diff |

Browser covers Knowledge Search, Evidence/Citation, Sufficiency/Fallback, READY, narrow-screen no-match, tenant A/B isolation, same-host Admin inspection and direct normal-user authorization negatives. LLM tests cover internal-only routing, redaction-required external routing, failed redaction preventing provider calls, restricted knowledge external denial and secret/error leakage negatives. Rule API tests consume existing H detail/new-version/validate contracts through the same trusted adapter; normal users cannot inspect/validate.

Fresh final runtime gate initially executed 369 tests; the added Rule adapter regression brings final full pytest to 370. Its initial failure exposed adapter route ordering (generic retrieval before Rule detail), corrected by using the unchanged production app's order. A repeat full run also used a smoke state file belonging to a different database; this invocation mismatch was corrected, without changing runtime assertions. The final 370-test run uses the final database's proven smoke state. Earlier B frozen-base guard adjustment and proof rerun are documented in track_b_integration_result.md. A frontend Rule test initially reused a consumed Response mock; fresh responses fixed the fixture. No test was skipped or weakened.

Known non-blocking warnings: existing Starlette 422 deprecation, SQLAlchemy pgvector reflection warning, and the existing enterprise build chunk >500 KB and existing locked ESLint version deprecation. Local tools used real PostgreSQL 17.11/pgvector, Redis and Chromium; remote CI uses its declared PostgreSQL 16/Redis service images. Deterministic LLM test adapters avoid external credentials; production identity/CSRF and ingestion deployment are not claimed.

The final npm ci uses a workspace-local cache because the sandbox cannot write the default home cache; install/typecheck/lint/unit/build then passed without lock drift.

Raw focused summaries, schema/runtime JSON, sanitized test logs and demo screenshots live under evidence/stage1-alpha/final. Historical original evidence remains under docs/delivery, verified by SHA-256.

Multilingual final gate: zh-CN/zh-HK/en-US each cover Knowledge, Evidence/Citation, Sufficiency/Fallback, Runtime and Admin; 262 UI keys per locale with mandatory build policy and six negative policy tests. Final backend rerun: 370 PASS, zero skips. See multilingual_frontend_result.md and evidence/stage1-alpha/multilingual for current logs, screenshots and the session/background refresh regression. The earlier final/ directory retains the pre-multilingual 46-unit/12-browser proof. Old exact-head frontend CI at 91cafd failed browser checks; no overall remote PASS is claimed for that SHA. Updated exact-head CI is recorded in the Draft PR/final response.

# M1 test/UAT result

Focused M1 tests: 13 PASS. Closure frontend: 76 unit PASS, npm ci/typecheck/lint/i18n/build PASS. Three catalogs × 341 keys, zero missing keys/hard-coded owned UI strings. Initial three-locale browser flows reached the final narrow-viewport assertion, which exposed unwrapped scope-grant tags; grid/form/table/tag sizing was corrected. The focused en-US case then passed end-to-end with zero retries. Exact-head CI reruns the complete three-locale UAT; its final outcome is attested in the Draft PR, without a self-referential commit SHA inside tracked evidence.

Initial local browser startup encountered Vite 504 after npm ci; restarting the owned dev server corrected the stale optimizer cache. Subsequent diagnosis used a focused layout probe and one-locale cases, without repeating full unit/browser matrices. Responsive assertions wait for layout transitions to settle and still require no page overflow. No security/result assertion was removed.

Real fixtures: existing Phase1E–I services persist Classification, APPLICABLE and INSUFFICIENT_EVIDENCE results, official-evidence-shaped synthetic originals, sufficiency and legal-basis identities in isolated PostgreSQL tenants. Loopback adapter composes existing production routers; it is test infrastructure, not production auth.

Browser matrix: four-step input/confirmation, unsupported action disabled, independent canonical result reads, evidence/source language, locale invariance/no writes, A/B direct API denial, identity/context reset and narrow viewport. No retry-dependent PASS. No full backend suite is manually run; only formal API/security probes necessary for this UAT.

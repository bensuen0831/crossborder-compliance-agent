# Multilingual frontend result

**Local multilingual gate: PASS.** The one canonical Track C H5 application supports zh-CN (Simplified Chinese), zh-HK (Traditional Chinese with Hong Kong UI terminology) and en-US (English). Track D Admin uses the same i18next instance and locale catalogs as M0. Each catalog contains 262 stable UI keys, with identical key sets and interpolation parameters; Ant Design receives the matching library locale.

| Locale | M0 Knowledge | Evidence/Citation | Sufficiency/Fallback | Runtime | Admin |
|---|---|---|---|---|---|
| zh-CN | PASS | PASS | PASS | PASS | PASS |
| zh-HK | PASS | PASS | PASS | PASS | PASS |
| en-US | PASS | PASS | PASS | PASS | PASS |

Typecheck, lint and the one production build PASS. Final unit tests: 63 PASS (46 prior integration tests, 10 multilingual tests, 6 negative build-policy tests and 1 background-session presentation regression). Real PostgreSQL/Redis/Chromium UAT: 36 PASS, four scenarios per locale repeated three times, zero retries/skips/flaky results. Sanitized logs, matrix summary and six locale screenshots are in evidence/stage1-alpha/multilingual. Prior evidence/stage1-alpha/final documents the earlier pre-multilingual gate.

Locale switching changes only stage1-alpha.ui-locale presentation preference, document language/title, translated controls and Intl formatting. Locale is absent from session identity, scope/retrieval query keys, request authority and Domain payloads. Each browser locale scenario switches through the other locales and back, preserving query text, Citation, Official Evidence original_text and AnalysisSnapshot ID; it rejects every extra API write. Existing backend codes such as INSUFFICIENT, lifecycle statuses and action codes remain unchanged. Unit tests also verify publication paths, action codes and record versions in all languages.

Official legal source language is independent of UI locale. Original source content, citation/provenance and snapshot identifiers are never translated or replaced. Content-language inputs remain language-neutral codes. Intl.NumberFormat formats counts/revisions; Intl.DateTimeFormat formats effective dates in UTC without changing source values.

I18N_METADATA_BACKEND_GAP: the frozen backend metadata/session contract offers display_name/name/code, without locale-indexed labels for business entities. Current backend-managed names are shown verbatim; stable IDs/codes remain fallbacks. Catalogs translate field names, controls and guidance, never country/scenario/product/data-category/capability/template/Knowledge business values. No second frontend business metadata source was invented. Actual owners: OTHER (existing metadata/registry API), M1 (Knowledge metadata), PRODUCTION (localized contract rollout). The current gap matrices record this explicitly.

The mandatory check:i18n script runs before build. It checks three-catalog parity, nonempty values, interpolation, all static/dynamic keys, visible React text/attributes/descriptors and forbidden translated Domain comparisons. Six negative tests prove violations fail the policy. Missing runtime keys emit I18N_MISSING_KEY and display a localized unavailable message, never a raw translation key. Error presentation also suppresses arbitrary sensitive backend error detail. Backend-managed text and neutral protocol/Domain codes remain data rather than UI-copy catalogs.

No dependencies or lock versions changed. package.json adds only check:i18n and its pre-build invocation using existing TypeScript and Node APIs. One package.json, lockfile, Vite build, React root, router, theme and session/API transport remain.

Prior exact-head frontend CI at 91cafd3860d66163a6fe83338e3e982f6390645b failed 5 of 12 browser cases while Query remained disabled. A deterministic regression showed background session refresh unmounted the workspace; keeping it mounted during background refresh preserves context while actual identity changes still clear caches/remount. One initial multilingual run passed 35/36: its trace showed a dropdown click had not selected context, with no scope request. The browser helper now uses the accessible keyboard selection path and still requires actual scope HTTP 200. The complete rerun passed 36/36 without retries. No authorization or tenant-isolation assertion was removed. Exact final-head remote CI is attested in the Draft PR and final checkpoint.

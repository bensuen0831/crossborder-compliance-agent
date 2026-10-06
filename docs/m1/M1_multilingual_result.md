# M1 multilingual result

Canonical i18next: zh-CN, zh-HK and en-US. All owned M1 UI strings have stable keys; governed labels prefer existing Phase1I metadata presentation and its deterministic fallback, with no frontend business dictionary or runtime LLM translation.

Locale is presentation state only, separate from official source/output-document language. Intl date/number formatting is reused. Result query keys omit locale; switching locale cannot execute analysis or write API facts. Missing static/dynamic keys fail the existing mandatory build policy, whose M1 coverage includes field/reference/flow keys.

Three locales, 341 keys each; mandatory static policy reports zero missing keys and zero hard-coded owned UI strings. All 76 unit tests pass, including 13 M1 tests. Focused tests and closure results are recorded in M1_browser_uat_result.md and the task checkpoint. Locale browser assertions preserve confirmations, canonical result identity and Official Evidence, and require zero formal API writes.

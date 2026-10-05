# Track D integration result

Source `22196955fb0167e3a5bce25bcdf9214f6ebeadb7`; merge `7ba0761c26609d0c6573005a22fcef9bab5feacf`. D focused backend wire tests: 2 PASS before consolidation. Delivery conflicts in files_created_modified.md and integration_handoff.md preserve both owners under docs/delivery. Backend source is byte-identical to the tested D source.

D modules and its 24 original unit tests moved into frontend/src/features/admin. The standalone package/lock/bootstrap/router/Vite/testing configuration was removed, with the original recoverable in the D merge parent. Shared C transport replaces the second fetch implementation, C session supplies optional trusted admin_context, canonical theme tokens style the feature, and C i18next supplies every owned Admin UI control/message via the same zh-CN, zh-HK and en-US catalogs. RuntimeStatus resets by version-key remount rather than synchronous effect updates, meeting the canonical hooks lint rules.

Rule inspection and persisted-test validation now consume existing H APIs. Rule authoring remains visibly unavailable in this screen. Missing ingestion deployment is gated by trusted ingestionAvailable (false unless explicitly supplied); no success is synthesized.

Before the multilingual extension: 46 unit tests and 12 browser checks passed. The expanded final three-locale matrix and current gate results are recorded in test_result.md and multilingual_frontend_result.md. Eight M0/session/security API tests include existing H Rule detail/validation and backend denial for normal project users. Full final Python count and runtime evidence: see test_result.md. No backend Domain changes or migrations.

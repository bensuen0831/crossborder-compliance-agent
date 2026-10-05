# Stage1-alpha integration design

Verified Phase 1H main/tag: `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7`; baseline CI 37254295087 SUCCESS. The start gate fetched origin, checked the exact main/tag/source heads and absence of the integration branch, and created a dedicated clean worktree. See evidence/stage1-alpha/start_gate.json.

| Track | Tested source | Merge commit |
|---|---|---|
| B / Phase 1K-A | 45af99271559ee6fd1f652e8ad169fc9afb11c55 | 13980c65fcdb6a7b6e15e9d413ea314a277069cf |
| C / M0 | 3f89f1e8f16402f4754b474260cb9022a4bf92c6 | fa09360f50a333e6a90e2577aa579524e89107e6 |
| D / Admin | 22196955fb0167e3a5bce25bcdf9214f6ebeadb7 | 7ba0761c26609d0c6573005a22fcef9bab5feacf |

Merges proceeded B → C → D with focused gates between tracks. Separate integration commits preserve/normalize delivery evidence, update the historical B validation baseline to the pinned H baseline, and consolidate D into C. Source ancestry and source branches are preserved: no rebasing, squashing, amending or cherry-picking.

B conflicts: files_created_modified.md, test_result.md. D conflicts: files_created_modified.md, integration_handoff.md. C: none. All conflicts were delivery documents; both owners' original bytes are archived under docs/delivery/{phase1h,phase1k-a,m0,admin-foundation}. SHA-256 proof is in evidence/stage1-alpha/delivery_preservation.json. No unexpected executable conflict occurred.

The canonical C AppShell owns one BrowserRouter, QueryClientProvider, theme, i18n and trusted session boundary. D is a feature below /admin, using the shared HTTP request function with same-origin cookies and safe errors. Backend APIs, repositories, registry, publication worker, model registry, RuleHit and formal Classification semantics are unchanged. Existing H Rule detail/validation contracts are consumed without a duplicate Rule engine or classification writer.

No migration or schema gap was introduced. Head remains 0008_phase1h; Architecture Rules 1–139 remain unchanged. No Phase 1I/1L domain or workflow work is included.

Production authentication, fine-grained contextual backend RBAC and ingestion infrastructure remain owned upstream capabilities. The demo uses the explicitly enabled loopback-only synthetic trusted-session adapter; it does not implement production login. Missing Admin capabilities remain unavailable or gated; see admin_backend_gap_report.md.

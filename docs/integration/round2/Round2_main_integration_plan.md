# Round 2 main integration plan

Authorized order: PR #18 (Phase1I) → PR #17 (Stage1-alpha) → PR #16 (Phase1L-A), merge commits only. The uploaded request is the release contract. No Phase1J, Phase1L-B, M1 or new legal/product behavior is authorized.

Start gate passed: main and Phase1H tag target 700951ebb9ebdf33e399158fd3fb53bb4a6c87e7; PR18 head 14cba25353d9ab7dda84e9620ff3197d9e2a3d1d; PR17 head 6c2aacd6475af0c0533717daa54b8e48946647e1; PR16 head 39be101e565fa4966e834180523f6ba47a96e5fc. All OPEN/DRAFT/unmerged/clean; main migration0008, architecture139. Exact source CI identities independently read through GitHub API. Raw evidence: evidence/round2-integration/start-gate.

Before each main merge, recheck main and the reviewed PR head. After each merge, capture actual resulting main, assert both-parent ancestry, execute exact-main workflow_dispatch and inspect underlying artifacts/logs. Use fresh disposable PostgreSQL databases for local backend gates. Existing migration tests independently archive the exact verified Phase1H main and compare fresh0009 with historical0008 upgrade, downgrade policy and equivalent catalogs.

PR17 and PR16 must first merge the preceding verified main into their source branch without rebasing. Archive both copies of the four known overlapping documents before resolving documentation conflicts. Stop automatic resolution on executable source conflicts. Any integration-only corrections require an explicit recorded review and independent exact-head CI; never disable gates or mask failures.

PR18 exact-main success permits v3.6-phase1i-pass only. PR17 requires backend and frontend/real-backend browser gates both on updated branch and post-merge main. PR16 requires semantic workflow/domain/locale review and backend/frontend validation on updated branch and final main. Browser UAT uses zero retries and all three locales.

Only after the final exact-main system gate and remote tag verification may v3.6-round2-integration-pass and Phase1J_repository_entry_decision.md certify repository entry. Keep historical source evidence immutable; record integration evidence separately and retain documented production gaps. Stop immediately on writer/head drift or actual regression.

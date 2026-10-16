# Current readiness and proposed deployment runbook

Current tools: existing Python3.12 virtualenv and dependency set, PostgreSQL17 with pgvector, Redis, Docker. S3/scanner/RAR/DOC converter are NOT CONFIGURED/VERIFIED. Runtime network uses inherited proxy/CA; keep TLS verification, never expose credential values. Current managed configuration has no declared new credential bindings. No environment draft fields changed for this D0.

For this audit, source/workspace/compliance-tools/runtime.sh; start only owned PostgreSQL/Redis services; use isolated kb01_d0_20261014 and explicit DATABASE_URL for fresh0020, not the retained compliance DB. The isolated audit is not production setup. Future reproducible install/start instructions must include real S3 versioning/multipart endpoint, scanner health, libarchive/container sandbox, converter, quota/storage paths and worker leases; save tested instructions in environment settings after owner-approved implementation. Capacity prerequisites: enough actual disk for compressed+expanded+multipart staging, object quota, gateway signed-part limits/expiry, extraction/process ceilings, no raw huge Git artifacts. Cleanup only task-owned temporary data; never purge retained evidence/source/history.


## Reproducible CI prerequisites and pending-member progress

The four existing complete-backend workflows retain `smoke/run_gate.sh` and all
assertions. Their KB prerequisites use `.github/actions/kb01-tools`: build the
explicit stdlib parser/archive source files with signed Debian packages; verify
the SeaweedFS 4.48 release digest; create private ephemeral credentials; enable
actual S3 versioning and exact-loopback signed-PUT CORS. Full regression fixtures
are explicitly `SYNTHETIC_SECURITY_SIGNATURES:EICAR_ONLY`; browser acceptance
separately downloads and verifies official main/daily/bytecode CVD signatures.
No untrusted original is mounted in the network-enabled trusted downloader.
Actual parsing/scanning/extraction remains offline, non-root and bounded.

The dedicated KB workflow preserves three independently measured parts: all
collected KB PostgreSQL/migration/security tests; complete frontend plus three
locale manager and catalogue Browser journeys; and four genuine capacity Browser
cases. Its aggregator verifies actual checkout SHAs, collected-versus-executed
test IDs, zero skipped/retried cases, all locale IDs and measured capacity kinds.
It does not replace the existing eleven mandatory regression workflows.

An extracted archive may legitimately be PREVIEW while its member uploads are
QUEUED_SCAN/SCANNING. Read-only batch projections now expose the canonical member
upload state, pending flag and mapping availability. The UI continues polling and
waits for verified members; final confirmation retains the same server CAS and
verified-original gate. No automatic retry impersonates human confirmation.

Generate one genuine capacity archive at a time with
`python scripts/kb01/generate_capacity.py --output <owned-directory> --kind <SINGLE|RAR4|RAR5|ZIP>`.
Every 540,006,868-byte PDF contains twelve actual RGB image streams plus page text;
archives contain exact real members, never sparse files or unused padding. The
capacity Browser suite records case duration, exact bytes/hash, batch/version IDs,
independent human publication, runtime READY and streamed original-download hash.
Only generated local archive copies may be disposed between serial CI scenarios;
canonical versioned originals and governance evidence remain intact.

Before a final acceptance claim, rerun from the sealed committed source. Current
development checkpoints are not borrowed as final-source evidence. F1 remains
BLOCKED — EXTERNAL_EVIDENCE_PENDING. No real-regulatory accuracy, production UAT,
paid-provider acceptance, main merge, release tag or Stage 2 is implied.

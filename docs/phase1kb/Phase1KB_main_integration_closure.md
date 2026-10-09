# Phase1K-B main integration closure

PHASE1K-B MAIN INTEGRATION = PASS. M2-E EXTERNAL AGENT API ENTRY = ALLOWED. STAGE1 FULL E2E ENTRY = BLOCKED UNTIL M2-E MAIN CLOSURE. Stage 2 = NOT STARTED.

- PR26 tested source: `d74bca4b61178637f24302d8b1fa6baa4f05ea59`
- Previous verified main: `efda0955342de8d1ea36aa0f754d63c9b421fec8`
- Normal merge / final tested main: `0f5a40c5ca3a8771624fb38e9380856d79e67342`
- Parents: `efda0955342de8d1ea36aa0f754d63c9b421fec8`, `d74bca4b61178637f24302d8b1fa6baa4f05ea59`
- Annotated tag: `v3.7-phase1kb-pass`; tag object `b5aacaf6af0ab526de25f6d06d195ef4ece92727`; dereferenced local/remote target `0f5a40c5ca3a8771624fb38e9380856d79e67342`
- Product tree byte-identical to PR source, full Git ancestry preserved, frozen0001–0015 unchanged, unique head0016←0015. Four V3.7 documents are present. No production source was changed during closure or recovery.

|Measured exact-main gate|Result|
|---|---|
|Backend full PostgreSQL suites|844 PASS; zero failed/errors/skipped/deselected|
|Architecture|269/269 PASS;242 existing+27 additive|
|Runtime|25/25 PASS; durable PostgreSQL checkpoint/restart/resume/idempotency|
|Frontend|130 PASS; typecheck/lint/build/i18n PASS|
|Browser|57/57 PASS; zero retries|
|Browser matrix|KB6; M2-D/C/B/A/M1 three each; original M0 matrix36|
|Locales|zh-CN / zh-HK / en-US PASS|
|Migration|Fresh→0016, exact frozen0015→0016, schema equivalence, empty downgrade/re-upgrade, authoritative-pin transactional refusal PASS|

## Exact-main CI and checkout proofs

|Workflow|Run|Checkout|
|---|---|---|
|Phase1KB Multi-provider LLM Governance|[37925455356](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37925455356)|`0f5a40c5ca3a8771624fb38e9380856d79e67342` SUCCESS|
|phase1a-runtime-smoke|[37925463749](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37925463749)|`0f5a40c5ca3a8771624fb38e9380856d79e67342` SUCCESS|
|M2D Governed Human Review|[37925472688](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37925472688)|`0f5a40c5ca3a8771624fb38e9380856d79e67342` SUCCESS|
|M2C Formal Result Workspace|[37925481453](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37925481453)|`0f5a40c5ca3a8771624fb38e9380856d79e67342` SUCCESS|
|M2B Production Document Integration|[37925489538](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37925489538)|`0f5a40c5ca3a8771624fb38e9380856d79e67342` SUCCESS|
|M2A Production Intake|[37925497299](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37925497299)|`0f5a40c5ca3a8771624fb38e9380856d79e67342` SUCCESS|
|M1 Intake Analysis Alpha|[37925507361](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37925507361)|`0f5a40c5ca3a8771624fb38e9380856d79e67342` SUCCESS|
|M0 Knowledge & Evidence Preview|[37925518471](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37925518471)|`0f5a40c5ca3a8771624fb38e9380856d79e67342` SUCCESS|

All eight runs are actual `workflow_dispatch` on main; all 11 jobs have checkout-log proof matching the merge SHA. Native KB backend/frontend artifacts independently assert expected source == runner checkout == final SHA; full JUnit records and logs were independently checked. No PR artifact or ephemeral merge-ref evidence is used for main gates.

## Capability / regression evidence

Canonical provider/model tables, LLM gateway and workflow runtime remain authoritative. OpenAI/GPT, DeepSeek, Qwen, GLM and OpenAI-compatible presets PASS **protocol-realistic local HTTP acceptance** through canonical adapters; paid Internet endpoints were NOT EXECUTED. AUTO, SINGLE, MULTI_MODEL, encrypted write-only Secret Boundary, immutable model/prompt/policy Snapshot pins, candidate-only document extraction and bounded same-scope knowledge-gap expansion PASS. No model words become legal evidence or formal decision authority.

RAG-FIRST, RULE-FIRST, EVIDENCE-FIRST and LLM-WHEN-NEEDED remain PASS; Classification, Applicability, CrossBorderAssessment, Obligation, Risk, FinalPath and RequiredDocument retain formal owner separation. Tests preserve M2-B stable canonical identity, exact immutable versioned snapshot state and version-scoped provenance. M2-D approval resumes the same Snapshot with owner re-execution; request-changes does not resume; input correction produces successor Snapshot; append-only decision history, CAS/idempotency, restart, actor authorization and historical immutability PASS. Detailed passed semantic test-case identities are retained in JSON evidence.

## Historical blocker and recovery

Initial eight main workflow runs failed before any job step due to GitHub billing/spending-limit admission. Original annotations and immutable BLOCKED evidence commit `5b60f2c6f6f41ade87e1254179932c790b582ef4` remain unchanged. User requested another execution; all eight workflows were freshly dispatched on the unchanged merge SHA and now completed SUCCESS. A temporary GitHub authentication interruption also prevented the final log capture; access recovered and all eleven checkout proofs were obtained without additional test executions. Its local immutable interrupted-state commit f0d99fee41b83162cd3a3e24ff121b6bcd40f0b8 is retained. This is infrastructure recovery, not browser assertion retry. Browser retries remain0; no tests/assertions/coverage/configuration were weakened.

## Evidence / scope limitations

- No paid Internet provider endpoints executed.
- Contract/static subset:477 PASS,7 skipped,360 deselected; this supplemental result never substitutes for complete844-test PostgreSQL runs, which require zero skips/deselections.
- Prior eight billing failures and all eleven zero-step job annotations retained.
- Five pre-existing Markdown double-space hard breaks cause baseline git diff --check warnings; production source is byte-identical to tested PR.
- No M2-E coding, Stage1 Full E2E or Stage2 started.

The immutable evidence branch descends directly from the tested main; its documentation commit is not a product baseline and does not advance main. Blockers: NONE. Next M2-E task must start from this exact merge SHA + `v3.7-phase1kb-pass`; this task stops without implementing it.

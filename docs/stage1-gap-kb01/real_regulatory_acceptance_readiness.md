# KB01-F0 / F1 acceptance boundary

The user confirmed that the reference Google Drive folder is a design/test reference, not a runtime dependency. No Drive synchronization, API integration, mandatory Excel manifest, repeated sign-in or permission bypass is required. Authorized real files will be supplied through the formal local-upload frontend after its implementation.

KB01-F0 is authorized: implement acceptance cases and Gold Standard templates; source/version/clause/expected-outcome structures; expert review records and approval flow; import interface; metrics, reconciliation and evidence schema. Synthetic data may verify these engineering mechanisms only. F0 is IN PROGRESS until these deliverables are implemented and tested.

KB01-F1 = BLOCKED — EXTERNAL_EVIDENCE_PENDING. No approved real-law Gold Standard, expert expected answers, reviewer appointment, or signed review/approval record has been supplied. Raw regulations, L1 fixtures, LLM answers and unreviewed extraction are not substitutes.

F1 start requires all five: authorized originals; verified source/version/effectivity; independently reviewed expected legal answers; formal reviewer identity/date/version/approval records; defined cases, jurisdictions and evaluation criteria. The project owner appoints and authorizes experts. The implementation must never imply approval from any university, organization or individual without those records.

A–E retain all original acceptance requirements, including six local formats, genuine >500MB single-file and >1GB RAR/ZIP import, persistence, clauses/citations, governance, scoped statistics, frontend, security and full regression. F1 does not waive any technical gate. A–E can independently receive Technical Acceptance PASS only after actual complete measurements.

Keep the KB01 feature branch and v3.7-stage1-e2e-pass unchanged; do not merge main, rewrite historical results or start Stage 2.


## Implemented F0 engineering contract (current feature source)

Four bounded typed payloads use the existing canonical MetadataDefinition /
MetadataVersion lifecycle: `REGULATORY_ACCEPTANCE_CASE`,
`REGULATORY_EXPERT_AUTHORIZATION`, `REGULATORY_SOURCE_VERIFICATION`, and
`REGULATORY_GOLD_REVIEW`. They are acceptance inputs and review records, not
formal legal results, a second knowledge store, a model registry, or M2-D review.
No new migration or historical rewrite is needed for these versioned records.

An appointment proposal identifies an actor and authorized jurisdictions; an
independent administrator must approve and publish it. The nominated expert
cannot approve their own appointment. Source and Gold approvals require that
exact currently authorized expert. Reviewer identity and timestamps come from
the existing server MetadataVersion approval fields. Neither an import body nor
a source URL supplies approval authority. The Gold record pins the exact case
payload, expected semantics digest, appointment version, source-verification
versions and original KnowledgeVersion/clause/content digests. L2 source pins
also require a genuine verified binary attachment. Synthetic records cannot
stand in for real-law appointment or source verification records.

The shared HTTP channel is `/api/v1/admin/knowledge-management/acceptance`:
`GET /templates`, `POST /records` (draft only), `GET /records/{version_id}`,
`POST /records/{version_id}/{submit-review|approve|reject|publish}`, and
`GET /cases/{case_version_id}/readiness?gold_review_version_id=...`.
Current `knowledge:acceptance:read/write/review/publish` grants are required in
addition to the existing Metadata lifecycle grants for mutations. No system
reviewer is constructed. Readiness uses the explicit Gold version, not latest.
A real incomplete case returns `BLOCKED_EXTERNAL_EVIDENCE_PENDING`; successful
record preparation could only allow independent acceptance to begin. It never
reports real legal acceptance or Production Business UAT as executed.

Generated JSON schemas and an unapproved template manifest are in
`acceptance-templates/`. Refresh with `python scripts/kb01/export_acceptance_templates.py`.
The generator supplies no fictional legislation, expert identity, expected legal
answer or approval. The evidence schema pins actual source, case, Gold, workflow,
snapshot and semantic digests; it cannot assert a legal PASS or start Stage2.

The reconciliation utility compares every declared semantic field, including
jurisdiction identities, reason codes, document requirement levels and exact
legal-source pins. Precision/recall and missing/unexpected counts are engineering
comparisons. Observations must come from authorized canonical result readers;
a comparison alone does not authenticate the observation or certify legal accuracy.

Focused measurements:7 F0 tests PASS; the combined F0 and retained taxonomy
owner regression has35PASS. Tests use explicitly labelled synthetic source and
appointment records. They prove the mechanism and refusal boundaries only.
F1 remains BLOCKED—EXTERNAL_EVIDENCE_PENDING. No real appointment, Gold Standard,
expert expected answer, real regulatory legal acceptance or Production UAT is
claimed. Final exact-head regression and evidence sealing remain pending.

The F0 readiness routes are composed before the generic metadata router in the
production application. They persist typed records only through the canonical
Metadata lifecycle, with current tenant/actor permissions and independently
approved exact source/expert/Gold references. Templates contain no appointed real
expert, approved real expected answer, or fabricated acceptance decision.

The current focused combined PostgreSQL run (64 tests) also retains existing
classification/document management regressions. F1 remains
`BLOCKED_EXTERNAL_EVIDENCE_PENDING`; no real regulatory or production business
acceptance has been executed.

### Exact identity naming compatibility

The readiness reader's internal parameter is `case_version_id`: it loads an
explicit canonical MetadataVersion, not a synthetic business fixture `case_id`.
No route, persistence identity, payload, decision or algorithm changed. The
original Stage1 ban on product fixture `case_id` logic remains intact, with no
checker exception or legal-owner whitelist. The initial v6 architecture failure
is retained in the private diagnostics; source is corrected and resealed before
full regression.


## Final F0 engineering readiness

F0 = PASS on 39c3581ca455df4e3ce9760ed2deab8905a5f588, measured by full exact-head CI and the explicit F0 test IDs in technical-closure/work_package_validation.json. This closes engineering readiness only. F1 remains BLOCKED—EXTERNAL_EVIDENCE_PENDING; none of the missing external originals, appointed independent experts, approved expected legal answers or formal approvals is invented. Real regulatory acceptance, paid-provider acceptance and production UAT remain NOT EXECUTED.

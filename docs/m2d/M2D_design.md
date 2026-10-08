# M2-D design

Baseline: `0dc005e583465a4604a5d40a369cb5fc2f0ccbef`, annotated `v3.6-m2c-pass`. D0 contract/matrix was committed before executable changes. D1–D4 backend checkpoint is `44b6233592d07973c9049a7f9c27e130c8d4da12`; D5 extends the existing H5 host. D6 requires the complete mandatory suite and exact PR-head CI.

The existing ReviewTask, ReviewDecision, ContextConflict, ProjectVersion, BusinessFact, AnalysisSnapshot, canonical graph, delivery service and PostgresSaver remain authoritative. Review services add current authorization, typed presentation, immutable decision history and relational successor lineage. No legal engines, permanent architecture rules, historical migrations, runtime adapter, provider/auth platform or package manifests are rewritten.

APPROVE is limited to explicit server-pinned requirement confirmation with no unresolved source conflict. REQUEST_CHANGES stays pending; REJECT holds the review boundary. Input changes use owning fact/product/intake services to construct a successor and execute the entire canonical workflow from requirement. Review comments never become facts. H/I/J/C0 recompute their own formal results. No direct final-result editing or graph jumps.

Scope gaps remain explicit: unsupported party/inventory/flow/jurisdiction/document correction, dependency-aware partial execution, multi-subject workflow, historical v1 authority, and Stage2. Legacy tasks are readable with capability-unavailable actions; they are never retrofitted.

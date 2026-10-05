# ADMIN_BACKEND_GAP — integrated reconciliation

Inspected against verified Phase 1H main plus tested B/C/D, not the older parallel-development base. RESOLVED means the specified contract exists and is consumed; it does not imply every Admin product capability is implemented. Backend source and migrations remain unchanged.

| ID | Actual contract / remaining gap | UI behavior | Status / actual owner |
|---|---|---|---|
| HOST-01 | Canonical C host/session/theme/API boundary | /admin embedded in the one C application | RESOLVED |
| AUTH-01 | Production identity/session/logout and deployment CSRF integration remain absent | Trusted host session required; explicit loopback UAT only; no production sign-in claim | PRODUCTION — identity/security deployment |
| RBAC-01 | Knowledge uses coarse knowledge:admin, no operation-specific backend grants | Server authoritative; project user without scope gets 403; no claim of fine-grained enforcement | STAGE1-BETA — Knowledge/security owners |
| RBAC-02 | No full org/department/project/resource effective permission service | Optional trusted host grants intersect current backend scopes; missing access stays closed | STAGE1-BETA — authorization foundation |
| LIST-01 | Generic Admin draft/search/pagination lists absent; metadata exposes active registry only | Known definition IDs and actual active projections | OTHER — Phase 1C metadata owner |
| VERSION-01 | Most generic resources lack new-version API for an existing definition | No invented version operation; Rule version API exists separately | OTHER — Phase 1C metadata owner |
| PAYLOAD-01 | Generic persisted history omits editable payload; model version numbers may be absent | Reloaded editor/diff disabled when payload absent; absent number shown honestly | OTHER — Phase 1C metadata owner |
| HISTORY-01 | Full Knowledge lists/history/diff/audit APIs absent | Inspect known version IDs and returned projections; unavailable history noted | M1 — Knowledge owner |
| WORKER-01 | Artifact storage and tenant-bound ingestion consumer deployment absent | Import disabled unless trusted ingestionAvailable=true; current UAT does not enable it | PRODUCTION — storage/worker deployment |
| UPLOAD-01 | Binary upload-to-Knowledge linkage absent | No binary upload or invented linkage | M1 — Document/Knowledge integration |
| SECURITY-01 | Full Knowledge write/read security policy metadata catalog absent | No editable sensitivity/external/download/retention profile; actual ingestion scopes remain visible | STAGE1-BETA — security/Knowledge owners |
| METADATA-01 | Product domain/tag, regulation and skills Admin routes absent | Clearly unavailable boundary screens | OTHER — metadata owners |
| COUNTRY-01 | Dedicated country/scenario governed configuration contract absent | Country configuration boundary only | PHASE1I — country/scenario contract owner |
| SCHEMA-01 | No server form/schema/resource catalog | Only known typed descriptors; no arbitrary schemas invented | OTHER — metadata/API owner |
| STATUS-01 | Generic resource publication-status API absent | Knowledge runtime status uses real endpoint; no invented generic sync status | OTHER — registry owner |
| RECOVERY-01 | No Admin reindex/recovery API | No recovery controls; existing outbox retries preserved | STAGE1-BETA — operations owner |
| RULE-01 | H Rule detail, new-version, validate/test and governed lifecycle APIs now exist | Consume detail/validate via existing endpoints; full backend regression proves lifecycle | RESOLVED — Phase 1H contract |
| RULE-UI-01 | Full Rule authoring screen is outside this consolidation | Explicit disabled authoring control, no fake success or classification writes | STAGE1-BETA — Rule Admin frontend integration |
| I18N_METADATA_BACKEND_GAP | Frozen metadata/session contracts provide display_name and codes, without a locale-indexed label contract for Country/Scenario/Product/Data Category/Capability/Template/Knowledge | Render backend-managed labels or neutral IDs/codes verbatim; translate UI field labels only; no frontend business translation registry | OTHER — existing metadata/registry API owners; M1 — Knowledge metadata; PRODUCTION — localized contract rollout |

Phase 1H solved the Rule API dependency, not production auth or Knowledge contextual RBAC. No new Registry, publish engine, model registry, legal engine or migration was created. Phase 1I remains owner of any future 0009/domain schema work; no integration schema gap requires a migration here.

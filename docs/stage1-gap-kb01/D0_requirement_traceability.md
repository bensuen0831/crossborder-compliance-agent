# KB01-MASTER V2.0 — requirement traceability

Main/tag060cbb5 remain verified. Existing commits6fb8b8d and56b0dfe retained. No related PR currently exists. Source-scope extension is additive and must preserve old APIs/FKs/rows. An actual destructive requirement will stop only that scope. No full KB01 acceptance is claimed.

| ID | Required capability | Owner/work package | Current measurement / remaining gate |
|---|---|---|---|
| KB01-01 | Country/territory/supranational/sub-jurisdiction CRUD, aliases, merge, deactivate/reactivate | Canonical Jurisdiction + Metadata / A,D | Existing governance; complete CRUD/impact/history pending |
| KB01-02 | Dynamic shared category CRUD, hierarchy/order/merge/reclassification | Existing Metadata / A,D | New technical feature pending, no fixed business category enum |
| KB01-03 | Document CRUD/version/eligible deletion/bulk archive | Existing Knowledge / A,D,E | Source/version owner exists; complete management pending |
| KB01-04 | Local six-format single upload>=500MB | S3 sessions / B,C | Not executed; Project100MiB policy not reused as large-file path |
| KB01-05 | Local multifile upload/common or per-item metadata | Batch/session / B,D | Pending |
| KB01-06 | Local folder upload/preserved paths | Batch/session / B,D | Full-path preview tested; actual upload pending |
| KB01-07 | RAR4/RAR5/ZIP, both RAR/ZIP>1GB | Isolated extractor / B,E | Not configured/executed |
| KB01-08 | OPTIONAL mapped XLSX/CSV; file/folder/archive-only import must work | Manifest/Batch / A,B | Native preview33 PASS; optional-column extension and import wiring pending |
| KB01-09 | Six-format/multilingual/RTL/OCR/clause parser | Document Intelligence/Knowledge / C | Existing Project adapters; shared source scope and remaining adapters pending |
| KB01-10 | Canonical database persistence/recovery | Knowledge + operational relations / A,C | Fresh baseline0020 PASS; additive revision pending |
| KB01-11 | Technical stages separate from governed review/publish/READY | Existing quality/review/outbox / E | Owners exist; complete binary journey pending |
| KB01-12 | SQL dynamic counts, distinct documents/versions/files/manifest and cross-tabs | Scoped query/statistics / D | Pending, no production sample-count constants |
| KB01-13 | Exact source version/run/object/article/citation provenance | Existing source/structure/citation / C,E | Project-bound parser mismatch documented; choose compatible optionA |
| KB01-14 | Genuine approved source integration with formal applicability/obligation owners | Existing formal core / F | No new engine; expert Gold Standard missing |
| KB01-15 | Source/destination/processing/storage jurisdiction comparison | Scope/Phase1I/formal owners / F | Retain multi-subject capability gaps; actual L2 acceptance pending |
| KB01-16 | Production auth/CSRF, operation RBAC, tenant/resource audit/security/holds | Existing security/host / A,E | Coarse admin alone insufficient; actual deployment provider/scanner missing |
| KB01-17 | Multipart/quotas/leases/restart/partial retries/cleanup/capacity | Operations / B,E | Existing PG/Redis ready; new large-file adapters pending |
| KB01-18 | Old mandatory IDs + new exact-head technical CI, Draft PR/no merge | QA/CI / E | Local preview only; old1012/361/25/142/77 floors not current measurements |

Mandatory order: A complete local/PostgreSQL gates -> B -> C -> D -> E -> F. UI navigation is Jurisdiction -> Category -> Document, with topic/language/format/issuer/legal effect/date/source/status/version facets. Excel and Drive are never runtime prerequisites.

The supplied Drive URL returned HTTP200 containing Google Drive Sign-in; no source listing/XLSX was accessible. Do not interpret HTTP200 as dataset access. Exact1026 file identities/counts and legal examples are NOT VERIFIED. No Google credentials were requested/copied. Real legal L2 requires actual authorized files and independent expert-reviewed expected outcomes; technical acceptance cannot substitute for that gate.

Report Technical Acceptance, Legal L2, Production Deployment Readiness and Production Business UAT separately. Stage2 NOT STARTED.


## Final independent technical closure at 39c3581ca455df4e3ce9760ed2deab8905a5f588

The opening entries are retained D0 findings. KB01-A–E and F0 technical gates are now PASS on the explicitly tested source; see final_acceptance_report.md and technical-closure/work_package_validation.json for actual IDs and measurements. F1 remains BLOCKED—EXTERNAL_EVIDENCE_PENDING. Production deployment readiness and production UAT are not accepted by these technical gates. No main merge, tag movement or Stage2 work occurred.

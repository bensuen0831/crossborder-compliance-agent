# KB01-D0 — requirement / owner audit

D0 inventory is COMPLETE. KB01-A through KB01-E are NOT COMPLETE. V2.0 authorizes continuing independent compatible work; source-scope compatibility is a tracked B/C dependency, not a blanket stop. Main/tag remain the validated 060cbb5 baseline. No release acceptance is claimed.

Authoritative sources inspected: Master V3.7 (general principles, production/browser, research knowledge and input requirements), Phase0 Parts20/20A/20B/20C/21/29/29A, ARCHITECTURE_RULES.md, current Knowledge/Document/Metadata/Scope repositories, APIs, parsers, Admin and intake UI, worker and original/reconciled Admin gaps. Master in this checkout ends at Part9A ProjectParty (999 lines); the requested later storage/operations parts are in Phase0. Neither document was modified. All findings describe implementation at the tagged source, not the old f563e50 gap report alone.

| Requirement / gap | Current finding | Classification | Owner / work package |
|---|---|---|---|
| Knowledge document/version identity | Existing knowledge_documents and knowledge_document_versions with source/collection/version | ALREADY_IMPLEMENTED | Knowledge / A |
| Source and governed collection | Existing sources, collection versions, bindings | ALREADY_IMPLEMENTED | Knowledge/Metadata / A |
| Jurisdiction metadata | Existing dynamic approved registry and Admin governance | ALREADY_IMPLEMENTED | Metadata / A |
| Regulation category, topic, language, issuer taxonomy | No registered Admin/metadata routes for these kinds | REGISTRY_METADATA_GAP | Existing generic metadata owner / A |
| AUTH-01 | APIs require trusted request.state.repository_context; no production browser identity adapter | DEPLOYMENT_GAP, RBAC_SECURITY_GAP | Identity/security; D/E prerequisite |
| RBAC-01 | Knowledge repo.admin checks coarse knowledge:admin for all operations | RBAC_SECURITY_GAP | Existing security/Knowledge owner / A/E |
| RBAC-02 | PermissionContext has scopes/tenant, no contextual resource-grant service | RBAC_SECURITY_GAP | Authorization foundation; A/E dependency |
| LIST-01 | Active metadata projections; no Knowledge source/document search/pagination | API_GAP, FRONTEND_GAP | Knowledge / A/D |
| VERSION-01 | Knowledge create_version exists; generic existing-definition version maintenance remains limited | ALREADY_IMPLEMENTED (Knowledge), API_GAP (generic) | Preserve Knowledge version owner / A/D |
| HISTORY-01 | Repo.compare_versions exists; list/history/diff API and complete UI absent | IMPLEMENTED_BUT_NOT_CONNECTED | Knowledge / D |
| WORKER-01 | Redis ingestion consumer exists separately; production S3/scanner/extractor not configured here | DEPLOYMENT_GAP | Storage/operations / B/E |
| UPLOAD-01 | Knowledge ingest accepts canonical nodes or JSON URL, not binary files | API_GAP, DATABASE_GAP | Knowledge + Document Intelligence / B/C |
| SECURITY-01 | No knowledge security/retention/hold policy catalog or controlled purge | RBAC_SECURITY_GAP, DATABASE_GAP | Security/Knowledge / A/E |
| METADATA-01 | Regulation boundary UI disabled; generic versioned registry is reusable | REGISTRY_METADATA_GAP, FRONTEND_GAP | Metadata / A/D |
| SCHEMA-01 | No server resource/form schema catalog | API_GAP, FRONTEND_GAP | Metadata/API; scope limited to KB dimensions / D |
| Actual 1,026-record XLSX and source archive | Not present in inspected repo/attachments; user-reported counts only | TEST_ACCEPTANCE_GAP | User-supplied real dataset |
| Configurable XLSX/CSV preview | New isolated pure application contract and native parser adapter, 33 tests | IMPLEMENTED_BUT_NOT_CONNECTED | A foundation delivered; not BatchImport persistence |
| Full path pairing/missing/unlisted/ambiguous | New parser preview supports path proposals and inventory reconciliation | IMPLEMENTED_BUT_NOT_CONNECTED | A/B |
| ManifestRecord/ImportBatch/BatchItem persistence | No tables or canonical application use cases yet | DATABASE_GAP, BATCH_IMPORT_GAP | A/B |
| Single binary Knowledge upload | Project upload is separate; Knowledge binary linkage missing | API_GAP, FRONTEND_GAP | B |
| Multi/folder upload | No Knowledge UI/session orchestration | FRONTEND_GAP, API_GAP | B/D |
| Resumable multipart | S3 adapter has only bytes put/get, no durable sessions/parts | LARGE_FILE_GAP, DATABASE_GAP | B |
| Pause/resume/retry/cancel/expiry/checksum/quota | No Knowledge session contracts | API_GAP, DATABASE_GAP, RBAC_SECURITY_GAP | B/E |
| 500MB+ documents | Project policy max100MiB; API materializes body | LARGE_FILE_GAP | B (do not raise Project cap as workaround) |
| RAR4/RAR5/ZIP extraction | No isolated archive adapter/task/contracts | BATCH_IMPORT_GAP, PARSER_GAP | B |
| RAR >1GB | No real capacity test or archive dataset | LARGE_FILE_GAP, TEST_ACCEPTANCE_GAP | B/E |
| Extractor isolation/bomb/link/path limits | Not implemented for Knowledge archives | RBAC_SECURITY_GAP | B/E |
| Knowledge PDF/DOCX/TXT parsing | Native Project adapters exist but are not wired to Knowledge | IMPLEMENTED_BUT_NOT_CONNECTED | Document/Knowledge owner gate / C |
| DOC/HTML/XHTML | No native adapters in default_native_parsers | PARSER_GAP | C |
| OCR fallback | PDF emits warning when OCR absent; not a completed scan-PDF acceptance | DEPLOYMENT_GAP, TEST_ACCEPTANCE_GAP | C/E |
| ParseRun/SourceTrace for tenant-wide Knowledge | Shared parser/trace DTO and FK require a Project DocumentVersion | OWNER CONTRACT REVIEW | See architecture_design.md |
| RegulatoryStructureNode/chunk/citation | Existing complete_ingestion creates canonical legal structure/citation/chunks | ALREADY_IMPLEMENTED | Reuse / C |
| Article extraction from binary originals | Current Knowledge work consumes already supplied nodes; stores reconstructed JSON | PARSER_GAP | C |
| Independent review/quality/publish | Implemented AdminChangeSet/AdminReviewTask and quality gates | ALREADY_IMPLEMENTED | Preserve / E |
| Reject review | Knowledge routes/transitions lack reject | API_GAP | Knowledge governance owner / E |
| Supersede/expire/archive | Existing transitions; archive only EXPIRED, no batch action | ALREADY_IMPLEMENTED (limited), API_GAP | D/E |
| Delete/restore/hold/reference checks | No authorized deletion/retention operations | DATABASE_GAP, API_GAP | D/E |
| Runtime readiness/publication outbox | Existing transactional outbox + publication worker | ALREADY_IMPLEMENTED | Reuse / E |
| Scope-first RAG/history | Existing approved pinned sources; archived/expired pins retained for replay | ALREADY_IMPLEMENTED | Do not introduce second retrieval / E |
| Admin six-tab CRUD | Current ID-driven screen, TXT1MB/text/URL import only | FRONTEND_GAP | D |
| Three-locale new UI | Existing locale infrastructure, KB controls absent | FRONTEND_GAP | D |
| Aggregate and cross-filter statistics | No Knowledge count/statistics endpoint | STATISTICS_GAP, API_GAP | A/D |
| Tenant/RBAC-scoped count reconciliation | Not implemented for new list/import/statistics | RBAC_SECURITY_GAP, STATISTICS_GAP | D/E |
| Retained 1012/361/25/142/77 coverage | Prior release floor; not rerun or claimed on this branch | TEST_ACCEPTANCE_GAP | E |
| Dedicated management + large-archive CI | Not added yet | TEST_ACCEPTANCE_GAP | E |
| Finite source-ownership successor | Current R3 approved overlay disallows new KB parser paths | OWNER CONTRACT REVIEW | Add bounded approved successor after design approval |

No hardcoded regulatory documents/countries were added. The new manifest parser has technical format identifiers only; metadata IDs must be supplied by the authorized registry adapter.

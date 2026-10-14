# V2.0 continuation decision

The user's KB01-MASTER V2.0 supersedes the earlier broad D0 pause below. Ordinary additive, backward-compatible extensions are authorized. Continue independent KB01-A work now; choose preferred optionA while preserving existing Project DTO/FK/API semantics. Stop only if implementation actually requires destructive cross-owner changes, a second authority, irreversible migration or external authorization. The observed source-ownership failure remains recorded; implement an explicit finite committed-blob KB successor without weakening historical checks. No additional approval is inferred for PR merge or destructive changes.

# KB01 architecture / compatible owner extension

## Concrete counterexample

A tenant-wide legal document can exist in knowledge_documents / knowledge_document_versions without any Project. At exact0020, documents.project_id is NOT NULL with FK to projects; document_parse_runs.document_version_id and source_trace_refs.document_version_id are NOT NULL FKs to Project document_versions. DocumentParserPort.parse and CanonicalStructureNode / SourceTraceRef require a document_version_id. KnowledgeVersion is not that identity. Fresh PostgreSQL inspection is preserved in database_owner_counterexample.json.

Calling a Project parser with a KnowledgeVersion UUID would produce a semantically false DocumentVersion reference. Creating a dummy Project would misrepresent authorization and retention scope. Adding a second regulatory file-version store would violate the user boundary. None was implemented.

## Preferred review proposal A — keep existing Knowledge owner

Keep KnowledgeDocumentVersion as the legal document/version authority and its immutable original_artifact_ref as original binary storage. Extend the existing KnowledgeIngestionRun to record parse attempt/profile/outcome and bind exact object version/hash. No competing ParseRun store. Introduce a neutral typed parser input/output contract with explicit PROJECT_DOCUMENT and KNOWLEDGE_VERSION source branches. Share parser algorithms through adapters; preserve the existing Project DocumentParserPort compatibility adapter and all R1/M2-B snapshot semantics.

For Knowledge, produce a typed source-trace projection from the existing KnowledgeStructureNode provenance plus genuine KnowledgeVersion/KnowledgeIngestionRun IDs, locator, original hash, immutable object version. Add a relational ingestion_run_id on the existing KnowledgeStructureNode rather than encoding a core relationship only in JSON. Keep RegulatoryStructureNode/Citation authority unchanged. Do not pass this Knowledge trace to an API requiring Project SourceTraceRef. V2 authorizes this compatible adapter option. Before claiming parser equivalence in package C, verify the genuine Knowledge ingestion/trace identity and preserve the existing Project DTO/FK contracts.

## Alternative B — generalize the shared Project document owner

Generalize Document/DocumentVersion/ParseRun/SourceTrace to typed PROJECT/KNOWLEDGE ownership, extend nullable/FK/XOR constraints and shared authorization. Requires larger changes to Project/Intake/Candidate semantics, active pointers, tenant hash uniqueness and retention. Not preferred; do not simply make project_id nullable or place a Knowledge ID in a Project FK.

## V2 source-scope verification

The initial D0 broad approval pause is superseded by V2. No destructive owner change is needed for option A. Ordinary additive KB management work continues. Actual second-authority, irreversible migration or destructive shared identity changes still stop the affected scope.

The finite KB successor authenticates source from a separately committed Git source SHA, preserves every historical manifest and all frozen migrations, and checks all paths outside its explicit set byte-for-byte. Negative tamper tests are mandatory. The initial architecture failure is retained as diagnostic evidence, not waived.

## Execution dependencies

D0 + V2 compatible owner decision -> A registry/operations identity + additive migration verification -> B real resumable S3/archive/worker -> C six-format canonical ingestion -> D six-tab UI and scoped SQL statistics -> E review/publication/RAG/history/security/full regression and exact-head CI. Independent parser preview is complete; full work packages are pending. No Stage2, direct main writes, tag changes or automatic merge.

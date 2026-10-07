# M2-B production document integration

Baseline `da2d420602d9c71991bcae4ffd3d33c9b3497d25`, annotated `v3.6-m2a-pass`; B1 source review is recorded in `evidence/m2b/b1_spec_review.json`.

Reuse canonical documents/document_versions/intelligence detail, DocumentParseService/native parsers, source traces, candidates, ContextResolutionService, ProjectVersion intake, AnalysisSnapshot parse pins and canonical Phase1L-B START/READ. No new graph, registry, legal engine or binary source of truth.

Authorized multipart upload validates a versioned server file policy and actual content, writes through ObjectStoragePort, and atomically attaches a canonical immutable DocumentVersion to a new draft ProjectVersion. API request idempotency stays in api_idempotency_records. A small FK relationship extension links an intake version to exact DocumentVersions; it is not a document/intake store. Existing project saves carry only these authorized links. Confirm freezes successful quality-gated parse runs and limits E candidate resolution to that exact universe. Structured and document facts use existing governed metadata, normalization, conflicts and ReviewTask.

Parse tasks remain canonical PostgreSQL document_parse_tasks. Authorized execution uses an atomic transaction and project/version guards, making duplicate delivery and process restart recoverable without committing partial candidates/traces. Missing scanner when configured policy requires scanning fails closed; a policy that explicitly does not request scanning records NOT_REQUESTED, never SCAN_PASS. Existing S3 infrastructure adapter is reused; a configured immutable filesystem adapter supports local/restricted deployments and empirical fixtures.

Step3 extends the existing H5 Intake component with upload/progress/list/parse/retry/unlink. Backend typed status and references remain authoritative. No Stage2 generation, result visualization, review UI, new production auth or LLM provider wiring. Later documents require a superseding intake version and new snapshot; old snapshots and input references remain immutable.

User-approved temporal correction: canonical DataItem identity remains stable; surrogate-PK immutable details provide exact inventory membership, versioned source/candidate/product/flow relations. Legacy unproven provenance is quarantined. Workflow uses the exact pinned context; single-item DATA_AWARE is executable, unsupported multi-subject input stops with typed capability gap. Implementation focused gates passed; complete closure is pending.

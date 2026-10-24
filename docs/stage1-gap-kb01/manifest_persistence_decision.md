# Manifest persistence decision — compatible KB01 operational extension

The existing bounded CSV/XLSX parser produces only immutable in-memory proposals.
The completed import batch owns its exact extracted/uploaded file inventory;
`KnowledgeBatchItem` requires a real upload and path. It cannot represent a
catalogue row whose referenced file is missing, a duplicate catalogue row, or a
revised explicit column/metadata mapping without pretending that a file exists.
The batch's inventory digest is immutable and must not be repurposed for this.

The Master V2.0 §12.3 authorization permits additive import/upload persistence,
with migration and recovery tests. The compatible next extension is
`0024_kb01_import_manifest_records`, parent 0023. It will add only operational
Manifest preview/row identities under the existing ImportBatch and UploadSession,
plus the bounded CSV/XLSX upload formats and canonical MANIFEST_IMPORT and
DOCUMENT_BIND admin receipt actions. DOCUMENT_BIND records human scope changes
through the existing KnowledgeBinding owner, not a second scope registry.
It will not add a Knowledge/Document/Registry/legal-result owner or change rules.
Historical 0001–0023 bytes remain frozen.

A Manifest preview will pin its exact verified original upload/version/hash,
batch inventory digest, explicit column mapping, governed metadata references,
server actor/time and idempotency payload digest. Individual immutable rows retain
row number, full normalized relative path, matched batch-item identity if any,
proposal fields, exact metadata refs, status and issues. Missing/duplicate rows
remain proposals and cannot create or publish knowledge. Only existing explicit
batch confirmation can create a canonical draft document/version.

CSV/XLSX are catalogue transport formats, never legal original document formats.
They cannot attach to a KnowledgeVersion or enter native legal-document ingestion.
The original six legal document formats and RAR/ZIP contracts remain intact.
Limits come from the existing governed KnowledgeManagementPolicy. Scanner, hash,
S3 version, tenant grants and immutable transport identity remain mandatory.

Migration safety requirements: fresh/current0023 schema equivalence; all existing
rows/digests unchanged; composite tenant/batch/row relations; immutable Manifest
records; safe empty downgrade; refusal if Manifest rows, new-format uploads or
related audit evidence would be lost. Downgrade never deletes authorization/audit
records to make itself succeed. Full acceptance and remote CI remain pending.

Explicit batch confirmation binds the canonical BatchItem to the exact ManifestRecord
through a tenant/batch-scoped relational foreign key. The bound row ID cannot later
change. Canonical KnowledgeVersion provenance retains those identities without
copying the catalogue payload into a competing metadata authority.

# Governed taxonomy CRUD

Canonical MetadataDefinition/MetadataVersion own category, topic, language, issuing-authority and related labels; JurisdictionEntity remains jurisdiction identity. Create/edit/aliases/hierarchy/merge/deactivation use the existing metadata lifecycle with separate submission, review and publication. Historical labels and jurisdiction identities never retarget to a merged definition. Current operation grants, tenant/project scope, CAS and idempotency apply before mutation.

Reference-aware deletion distinguishes eligible unpublished drafts from published, referenced or held records. History and merge aliases remain auditable. The frontend uses published canonical tree/options, shared AdminShell and all three locales. Actual country/category Browser coverage creates and edits versions, reviews/publishes independently, verifies protected deletion and reload.

Detailed contracts: [classification registry](classification_registry.md), [API contract](api_contract.md), [deletion governance](deletion_governance.md). Final-head evidence remains required; a successful development journey is not remote closure.

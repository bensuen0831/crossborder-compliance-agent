# M2B document linkage result

Document/DocumentVersion/intelligence tables remain canonical. A ProjectVersionDocumentLink FK relation captures exact intake-version attachments, not a second document store. Upload/save/unlink creates new immutable draft versions; confirmed input requires explicit supersede. Hash/request retries reuse identities; same document name produces a real new DocumentVersion.

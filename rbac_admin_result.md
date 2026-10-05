# Admin RBAC result

The feature accepts the host's trusted effective context rather than a browser-editable role picker. Per-resource grants separate `VIEW`, `EDIT`, `REVIEW`, `APPROVE`, `PUBLISH`, `ARCHIVE`, `DOWNLOAD`, `EXPORT`, and `OPERATIONS`. Existing API scopes are required in addition to those grants. Unimplemented download/export/recovery APIs expose no actionable controls.

Phase 1C currently uses `metadata:admin`, `metadata:review`, and `metadata:publish`. Phase 1F/1G Knowledge governance uses `knowledge:admin` for all actions. The UI separates controls even when the backend scope is shared. Backend operation-specific Knowledge grants and department/project resource authorization remain gaps; the UI cannot enforce them against direct HTTP callers.

The host passes tenant, organization, department and project context plus actor/roles for display and effective grants for decisions. Changing the context clears selected data/drafts. Neither tenant IDs nor grants are sent as authentication headers. The transport uses same-origin credentials and can be replaced by Track C's authenticated/CSRF-aware fetch implementation.

Automated evidence includes hidden publish controls for a project user, permission checks requiring both effective grants and API scopes, host-login boundary, tenant-context reset, backend 401 without trusted context, backend 403 for unauthorized metadata/Knowledge publish, backend 404 for cross-tenant Knowledge reads, and rejection of same-author Knowledge approval. UI hiding is not reported as backend authorization.

# Knowledge operations UI result

One Knowledge page uses existing Phase 1F source/document/version and ingestion endpoints. It creates a source, opens/updates supported source configuration, creates a document or opens a known ID, and creates a governed knowledge version. Source metadata/provenance and scope permission strings are explicit user-maintained metadata; the UI does not invent policy values.

Import supports UTF-8 plain text (1 MB limit) converted into the existing canonical `OTHER` node contract, pasted text, or a controlled HTTPS URL accepted by the backend downloader. This is not a binary PDF/Word-to-Knowledge upload integration. Scope selections for jurisdiction/product/scenario come from backend registry responses. The supported API scope-type literals are shared protocol values, not hard-coded business option lists.

Bindings are persisted by ingestion and inspected through the existing bindings endpoint. Product-specific and country-scoped content use those dimensions. Other product dimensions await metadata list contracts. The request key is retained across retries and can be renewed for a new import. Durable ingestion status polls automatically, and completion reloads the version/bindings. Quality evidence is available through the existing quality endpoint; a failed validation does not expose approval/publish controls.

The ordinary UI flow is import → validate → submit-review → independent approval → publish → automatic runtime observation. Real API tests used the existing Redis queue, ingestion worker and publication worker, with a test-only artifact store. The source was explicitly marked VALIDATED through its existing update API. No manual sync action is part of the flow.

Production ingestion requires the existing worker to be deployed per tenant with an actual S3-compatible artifact store and approved downloader destinations. That operational integration was not fabricated in this frontend branch; see the blocker in `admin_backend_gap_report.md` and demo prerequisites.

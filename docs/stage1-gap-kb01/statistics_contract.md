# SQL statistics / reconciliation contract

Counts distinguish manifest rows, distinct canonical documents, immutable versions, uploaded physical artifacts, uploaded bytes, missing files, parse successes/failures, pending reviews and active/expired/archived versions. Never equate Excel records with actual uploaded sources or distinct regulations. Query authorized tenant/resource set first, then aggregate; enforce identical filters for lists and counts. Stable pagination and explicit reporting cutoff avoid cross-page races.

Group by governed jurisdiction/category/topic/language/format/state and requested combined dimensions. M:N dimensions use COUNT(DISTINCT canonical identity) per group; group totals are not blindly summed as global totals. Technical batch status and legal publication lifecycle are separate columns. Deletion/archive/retry/version publication update counts transactionally or via verified rebuildable projection; compare SQL base data against API after each mutation. No1026/24/884 production constants.


## Final counting contract

GET /statistics preserves the authorized list query and projects all-version lifecycle counts, parse-run outcomes, representative-document language/format/classification groups. Import inventory is separately labelled TENANT_OPERATIONAL_UNFILTERED and requires current batch-read, manifest-read and upload-read grants; unavailable inventory is null, not a fabricated zero. GET /statistics/cross-tab supports category/topic/language/format/status/source, tenant/document authorization, the same exact representative versions, SQL COUNT(DISTINCT document_id), pagination and missing-dimension exclusion. Many-to-many cells cannot be summed into a global regulation total. The UI and published taxonomy tree use these backend projections.

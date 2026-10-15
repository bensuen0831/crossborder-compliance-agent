# Knowledge Operations frontend plan

Extend existing/admin Knowledge Operations under the same session/theme/Admin shell. Six tabs: documents/list/detail/search/filter/pagination/preview; single/multi/folder uploads; manifest+RAR/ZIP batches/mappings/progress/errors; dynamic metadata; version/history/diff/review; scoped statistics. React controls use backend metadata and allowed_actions only. No UI legal interpretation or country dictionary. Upload controls expose bytes with explicit units, pause/resume/abort/expired sessions; reject unsupported storage/extractor/scanner honestly.

Typed metadata form: title, jurisdiction/category/topic/language, authority, regulation number, official HTTPS source, publication/effective/expiry dates, source notes and verified detected format; lifecycle read-only. Destructive actions require reason/impact/hold and server authority. All new UI text zh-CN/zh-HK/en-US. Current screens remain unchanged pending owner gate; no Browser acceptance is claimed.


## D management source checkpoint (technical acceptance still in progress)

The existing AdminShell now mounts the regulatory management channel. It queries
current server operation capabilities without treating legacy `knowledge:admin`
as a grant. Document list and SQL statistics share the same scoped filters;
classification totals disclose many-to-many counting. Exact-version clause
previews are paginated and render source as text with original citation identity.
Original downloads read verified S3 object versions in bounded chunks, force
attachment/octet-stream, and require both read and download authorization.

The channel supports metadata editing, new version proposals, taxonomy aliases,
review/publication actions, reference impact, and merge proposals through existing
owners. Version CAS is separate from definition CAS. Editing retains exact labels
that are absent from the first options page. Transfer computes SHA-256 in a Worker,
reads the file stream incrementally, and uploads bounded signed parts without
application credentials. Resume state retains only an opaque upload identity.
Batch reads are durable, paginated, and refreshed while active. Technical item
retry keeps one canonical ingestion run and cannot retry permanent extraction
refusal. Failure exports have a separate grant and verify the batch revision.

Measured focused owner tests:39PASS. Frontend full regression:150PASS (all142
pre-existing plus8additive tests). Typecheck/lint/build/i18n passed. Browser
acceptance is not yet rerun for this source, and these measurements do not mean
KB01 A–E Technical Acceptance PASS. Source/collection selection UX, full-capacity
canonical import, translation alignment, deployable CI provisioning, F0 engineering
and full exact-source acceptance remain open. F1 remains externally blocked.

The isolated preceding C full run recorded1209PASS/5FAIL. Four were PostgreSQL
`md5` DDL emitted into SQLite-only runtime boundary fixtures; the model now limits
PostgreSQL-specific DDL to that dialect, preserving PostgreSQL constraints and
frozen0023. The fifth was absent TypeScript tooling in the isolated checkout;
its exact lock was installed and the existing real TypeScript SDK business test
then passed. Original failures remain archived and are not overwritten.

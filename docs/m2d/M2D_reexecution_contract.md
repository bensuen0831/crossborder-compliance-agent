# Resume and controlled reexecution

APPROVE is limited to explicit server-pinned requirement confirmation with no unresolved context/conflict. Its canonical immutable decision is committed before delivery. Same-snapshot resume revalidates current authorization and reexecutes the interrupted owner; it cannot jump to a downstream stage.

REQUEST_CHANGES remains PENDING and does not resume. REJECT closes the review boundary without converting ordinary rejection to infrastructure FAILED. Input-changing correction uses a successor snapshot and full canonical restart from requirement; dependency-aware partial rerun is unavailable.

If approval delivery fails after commit, authorized original reviewer can invoke body-free POST /reviews/{id}/resume. The server loads the original immutable decision; no browser actor/thread/stage/token is accepted. Restart and duplicate delivery preserve workflow/checkpoint/history identity.

Focused WIP evidence: 70 tests in artifacts/m2d/d1-d4-checkpoint2.log plus owning cross-border review test in d4-formal-review.log. Migration measured dual-path JSON is artifacts/m2d/migration_dual_path.json. Full closure and exact-head CI remain pending.

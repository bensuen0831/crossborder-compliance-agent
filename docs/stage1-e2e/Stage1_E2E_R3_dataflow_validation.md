# Stage1 E2E R3 — dataflow validation

Typed flow input uses the existing application owner and ContextResolutionService. Assertions require persisted source and destination nodes, edge, item link, different jurisdictions, exact context/snapshot versions, same subject/scheme classification in both jurisdictions, and same-jurisdiction applicability isolation. The existing multi-subject capability boundary remains explicit; no 0021 or additional runtime is introduced.

Final exact-head measurements: PASS on `25b2cb34be24578c74ea7ed4931f9534ff0289f3`; see `Stage1_E2E_R3_test_result.md` and the adjacent R3 evidence files. Only L1 synthetic governed acceptance is covered.

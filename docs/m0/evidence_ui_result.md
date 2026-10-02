# Evidence UI result

EvidenceCard and library EvidenceTable consume existing EvidencePackItem. A canonical locator
is the heading because the backend DTO does not expose document title. The UI shows source URL/
authority, internal/external type, source tier, jurisdiction where available, scope-validation
status and the backend evidence count. Context scope is shown separately rather than invented
per-item product/scenario bindings.

SourceCitationDrawer shows citation ID and locator, source authority/tier, effective dates,
knowledge or external-evidence version, index/policy/snapshot pins, content hash, authorized
original excerpt and backend provenance. Text is React-escaped; source links require HTTPS
without embedded userinfo, use noreferrer and open in a separate tab. There is no raw HTML or
LLM narrative parser. Backend return values are never converted into legal conclusions.

Runtime status consumes the existing Admin readiness endpoint only when the session indicates
knowledge:admin; the backend still enforces the permission. Published version, READY/PENDING/
BUILDING/FAILED, FTS/index/graph/registry/cache checks and reason codes are visible. No embedding
configuration is shown explicitly as Vector NOT_CONFIGURED, not a fabricated vector PASS.
M0 does not expose sync/reindex or duplicate Track D CRUD forms.

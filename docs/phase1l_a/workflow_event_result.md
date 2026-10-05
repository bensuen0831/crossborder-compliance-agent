# Canonical workflow events

Nodes use existing canonical_event and RuntimeOperationsPort.record_event, with deterministic workflow/step/visit keys. Existing WorkflowEvent storage remains authoritative. Tenant-scoped runtime stream_events reads that same store after fresh authorization and reconstructs WorkflowEventDTO only; raw runtime events never escape.

WAITING, RUNNING, COMPLETED, WARNING, REVIEW_REQUIRED and FAILED are explicit status values. Canonical payloads contain structured reason codes, status and request_id only; no raw evidence/provider response/error text. Status/request_id are persisted in the existing payload JSON without migration. WARNING uses NODE_PROGRESS rather than falsely marking the workflow COMPLETED.

Domain event enum/contracts and the default smoke stream behavior remain unchanged. Replay preserves event identities; process tests verify unique IDs, workflow correlation and denied cross-tenant streams.

Locale supplement: the existing event adapter now rejects unknown/localized lifecycle
statuses, mismatched payload status and non-code reason_codes. All six supported lifecycle
codes retain their exact values. Presentation/API consumers generate localized labels outside
the Workflow Domain. Event generation does not inspect preferred_locale; tests compare
event identities, types, node/status codes and structured payloads across zh-CN / zh-HK /
en-US, excluding normal wall-clock audit timestamps from independent execution comparison.

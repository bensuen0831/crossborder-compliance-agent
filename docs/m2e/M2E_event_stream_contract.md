# SSE and WebSocket

SSE GET `/api/v1/external/workflows/{run}/events`, WS `/api/v1/external/ws/workflows/{run}` require Authorization Bearer header. Browser integrations should use secure server clients; never put tokens in URLs. Last-Event-ID supports replay cursor on both transports.

Both serialize the same versioned ExternalWorkflowEvent from canonical WorkflowEventDTO: event_id, schema_version, event_code, timestamp, project/run/snapshot IDs, compact status/step/reason refs, result/review refs, correlation_id. Streams are bounded by duration/batch policy, revalidate live credential and binding, and close on terminal/review states. Reconnect resumes canonical events; no raw LangGraph/checkpoint/model payloads.

WORKFLOW_PROGRESS is presentation of NODE_STARTED/PROGRESS/COMPLETED. REVIEW_REQUIRED exposes a safe task reference; no external review decision endpoint bypasses M2-D. Status/read remain canonical WorkflowView/Stage1ResultService.

# Canonical workflow state

ComplianceWorkflowState is the checkpoint wire shape. StateEnvelope validates it with extra fields forbidden, UUID-only result/fallback/review refs, at most sixteen result/visit/completed entries, bounded counts and structured reason codes. ExecutionIdentity carries workflow, tenant, project, snapshot and opaque request-context IDs, mode and all four version reservations.

References use SemanticStep as the map key: formal-context/data-flow refs point to owning services, retrieval/sufficiency/fallback may reference the persisted retrieval run containing RAGContextPack and ActionableFallbackGuidanceContext, classification points to the canonical classification_result_id. No new fallback/result store is created. Resolution and permission checking belong to each owning service.

No ORM, session, repository, client, secret, document body/binary or chunks are allowed in state. Factory dependencies remain outside the checkpointer. Runtime entry and every stage validate identity against fresh authorization. Initial state must exactly match the server-generated empty envelope; arbitrary client progress/ref injection is rejected.

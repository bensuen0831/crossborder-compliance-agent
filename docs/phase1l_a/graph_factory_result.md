# Graph factory

LangGraphWorkflowRuntimeAdapter accepts an optional graph_factory. None preserves the original Phase 1A graph and its configuration. CanonicalGraphFactory builds the single sixteen-step graph plus human_review and finish using the existing adapter runtime import boundary. Official PostgresSaver and setup remain owned by the existing adapter.

Canonical configuration keeps workflow_run_id == thread_id and configurable recursion bounds. Pipeline order is tuple(SemanticStep), not a frontend stepper. Graph/state versions are phase1l-a-canonical-v1 and phase1l-a-references-v1; mismatched persisted versions fail before execution. Runtime/checkpointer versions remain separate from snapshot/legal configuration pins.

No second runtime/store/checkpointer schema or dependency is introduced. Repeated start with an existing canonical checkpoint returns the authorized current status instead of re-executing the initial stage. Failed, warning or completed terminal resumes do not execute another stage.

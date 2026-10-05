# File inventory

New application files: workflow_skeleton.py and workflow_classification.py. New workflow file: workflows/canonical.py. New infrastructure file: persistence/workflow_authorization.py. New tests: phase1l_a_worker.py, test_phase1l_a_skeleton.py, test_phase1l_a_contracts.py. These are orchestration contracts, bindings, authority integration and synthetic test helpers, not new domain legal implementations.

Modified existing files: application/ports.py, workflows/langgraph_adapter.py, persistence/runtime_operations.py and persistence/repositories.py. Changes are optional factory injection, backward-compatible review metadata, status forwarding and reading the existing canonical event store. Default smoke behavior remains preserved. Shared runtime changes require integration awareness by other tracks.

Thirteen delivery documents are in docs/phase1l_a to preserve earlier root reports. Measured validation is in evidence/phase1l_a; raw logs are ignored artifacts. No migration, Architecture Rules, frontend, rule engine, retrieval/knowledge/config registry, dependency manifest or other track implementation is changed. Exact inventory: git diff --name-status 700951ebb9ebdf33e399158fd3fb53bb4a6c87e7 HEAD.

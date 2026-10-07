# M2-B WIP handoff — BLOCKED

Baseline `da2d420602d9c71991bcae4ffd3d33c9b3497d25` / annotated `v3.6-m2a-pass`; dedicated branch `milestone-m2b-document-binary-integration`. M2-A source branch remains frozen. B1 supplied-spec review PASS.

Preserved WIP: authorized multipart binary upload; canonical Document/DocumentVersion persistence; immutable draft-version attachment links; generic configured content policy; existing object-storage port with local adapter; honest scanner capability handling; existing durable parse tasks/native parser; genuine SourceTrace and candidates; restore/idempotent parse; controlled supersede/unlink/replace API.

Focused PostgreSQL/storage/security tests: 11 PASS. Snapshot-contract diagnostic: 1 PASS **reproducing a blocker**, not acceptance. See [contract blocker](M2B_contract_blocker.md) and [measured checkpoint](../../evidence/m2b/implementation_checkpoint.json).

WIP linear migration `0012_m2b_document_inputs` follows `0011_m2a_intake`; fresh focused PostgreSQL upgrade succeeded. Frozen 0001–0011 unchanged. Migration dual-path/equivalence/downgrade/re-upgrade closure is pending. Do not claim migration or M2-B PASS.

Pending: owning E/F/H/I version-contract decision, exact document/parse universe and readiness confirmation, snapshot-scoped context reads, historical workflow authorization, governed document fact binding where necessary, existing Step3 H5 integration/client generation, all remaining focused acceptance tests, ownership/architecture checks, full backend/frontend/browser/migration closure and exact-head CI certification.

No frontend modification; no new legal engine, graph/runtime/checkpointer, competing Project/Document/Fact/Snapshot store or fake provenance. Production malware/queue provisioning is not claimed. No M2-C entry decision, no merge and no later-phase work.

Task checkpoint: `artifacts/m2b/phase_progress_checkpoint.md`; original blocked checkpoint/inventory are retained. Frozen-source identity and measured logs are under `evidence/m2b/`.

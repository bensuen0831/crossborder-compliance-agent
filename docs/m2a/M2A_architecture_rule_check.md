# M2-A architecture checks

Baseline `83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1`; preserved WIP `325b4a6c0ca3a6f4f0d58552634bcc7dcadca24b`. Implementation source is pinned in `evidence/m2a/approved_owner_overlay.json`. Full closure/exact-head CI are required before an overall PASS.

ARCHITECTURE_RULES1–155 remain byte-identical to verified baseline. Existing151 assertions are preserved; scripts/m2a_architecture_check.py adds13 M2-A checks (draft/formal, confirmation/snapshot, exact intake pin, single project/intake sources, frontend authority/decision exclusion, registry metadata, tenant isolation, authorized workflow snapshot, request authority rejection, genuine provenance, controlled insufficiency). Functional PostgreSQL tests corroborate these boundaries; a frontend authority-injection tamper test rejects violations.

scripts/m2a_ownership.py authenticates a finite set of shared files against immutable committed Git blobs, preserves ancestry and historical0001–0010, domain engines, canonical workflow/runtime/checkpointer, architecture rules and frontend dependency tree. Historical J/L-B/M1/K-A/Stage1 ownership checks consume only this proven finite overlay. Original approval manifests/source commits remain intact. Unrelated/malicious paths and unverified baseline records are rejected; no broad future waiver.

Overall certification requires existing151/151 + M2A13/13, K-A boundary and Stage1 integrity, mandatory runtime25/25, full no-skip backend regression and exact-head CI.

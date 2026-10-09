# Model selection contract

The project-scoped eligible catalog is an advisory backend read using the existing ModelRegistry, tenant/project ModelUsagePolicy intersection and ModelRouter. It validates current tenant/project permissions, capabilities, health and enablement. A draft read writes no Snapshot pins. Intake business categories are not security grades; unresolved protection labels retain internal-only semantics.

AUTO carries no model IDs. SINGLE carries one eligible identity, revalidated at invocation without another-model fallback. MULTI_MODEL requires ENHANCED and2..N distinct eligible IDs; N is the pinned invocation policy limit. Each child has independent request/audit identity. Group outputs remain DERIVED_CANDIDATE; no vote or legal result authority exists.

K-B5 focused real PostgreSQL gate:16 PASS (4 catalog checks +12 existing K-A configuration checks). K-B6 real two-provider HTTP AUTO/SINGLE A1/SINGLE B1/MULTI A1+B1 and audit6 PASS; snapshot/intake/K-A/M2-D29 PostgreSQL PASS; three-locale Admin/User smoke6 PASS. Full closure and exact-head CI remain mandatory and pending.

# Forward-only successor snapshot

Source review/run/snapshot/context and formal results remain unchanged. The existing Project aggregate appends a DRAFT version, validates/confirms it, pins the exact source DocumentVersion/ParseRun universe and unchanged analysis_as_of_date, and creates a new canonical snapshot/run. ReviewCorrection records typed lineage and selected source identities; input values remain in canonical Project/BusinessFact stores.

The source ReviewTask remains at its original review boundary. SUPERSEDED is a backend presentation derived from immutable correction lineage. This preserves complete S1 Stage1-result semantics after S2 finishes. Duplicate correction reuses the same successor identity and revalidates current permissions before delivery.

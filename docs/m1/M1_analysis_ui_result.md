# M1 analysis UI result

Existing authoritative result references are read independently; no frontend classification/applicability engine or workflow graph exists. Canonical IDs, reasons, category/level, rule hits, evidence references, review/conflict state, source/regulation version, legal-basis IDs and snapshot/version audit references are displayed.

Reuse: EvidenceTable, SourceCitationDrawer, SufficiencyPanel and FallbackPanel. Official source language is now explicit in the shared drawer. Excerpts and citations remain original, separate from UI language. Legal-basis detail/catalog absence is recorded; no reconstructed legal text is invented.

All six Applicability states are renderer-tested; unrecognized statuses remain neutral. Backend read failures, empty/missing results and insufficient evidence do not imply a legal outcome. Project-level current context/flow views are explicitly distinguished from snapshot-pinned results.

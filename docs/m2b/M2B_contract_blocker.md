# M2-B frozen snapshot / inventory contract blocker

`HIGH_REASONING_ESCALATION_REQUIRED — M2-B = BLOCKED`

B1 supplied-spec review passed. This is a newly reproduced implementation conflict, not the former missing-document blocker. M2-A main/tag remain verified and unchanged. No M2-B closure or entry decision is issued.

## Exact empirical counterexample

Real PostgreSQL, real DOCX, existing native parser and E normalization:

1. Create a new production Project/Intake; upload DOCX with `Field` / `Type` table headers; parse into genuine traces/candidates; confirm intake v2.
2. E creates formal `field` and `type` DataItems with resolution detail version 1. Snapshot S1 pins inventory version 1. H accepts `field` under S1 with the existing authorization/configuration.
3. Supersede confirmed intake; replace the same canonical Document with different real bytes, producing a new DocumentVersion; parse; confirm intake v4.
4. E context run 2 pins inventory version 2 to S2, but reuses the same formal `field` ID and retains its sole resolution detail at version 1.
5. H preparing the same formal item under S2 raises `LookupError: classification resource not found`. S1 still passes its version check, while the shared item provenance links now also include the later document's trace.

Measured IDs and versions are in [snapshot_contract_probe.json](../../evidence/m2b/snapshot_contract_probe.json). The probe passes by asserting the rejection and provenance growth; it does **not** establish successful M2-B acceptance. Eleven upload/storage/parse/security focused tests passed independently. No full closure was run.

## Exact current contracts

- `context_models.py:DataItemResolutionDetailEntity`: primary key is only `data_item_id`; `version` is a scalar column. There is no second historical detail row for the same ID.
- `context_repositories.py:create_formal_data_item`: tenant/project/canonical-name match returns the existing ID before recording the new version's detail.
- `start_context_run`: increments the context version and sets `data_inventory_version` to that version. `pin_snapshot_context` preserves it immutably.
- `attach_candidate_to_data_item`: appends candidate/source-trace links for the same formal ID without inventory-version qualification.
- H `classification_repository.py:_prepare`: requires `detail.version == pin.data_inventory_version`, failing closed on mismatch. `document_evidence` follows item trace links without a snapshot argument.
- F `knowledge_repositories.py` and I `country_compliance_repository.py` also fetch detail by item ID and require equality to the pinned inventory version. This is a shared frozen contract, not only a workflow-node issue.

These E/F/H/I files and frozen migrations 0001–0011 are byte-identical to verified M2-A main; [identity proof](../../evidence/m2b/frozen_contract_identity.json) rules out a new M2-B change to these contracts.

## Conflict with approved authority

Supplied Phase0 V3.6 Part13 requires “Immutable Version + Active Pointer / Status”; Part22 requires immutable version tables. The user's M2-B confirmation/snapshot requirement pins exact document/parse/formal-input identity and preserves old snapshots after later uploads. Current E identity reuse, single-row detail and unversioned provenance cannot represent both S1 and S2 while retaining F/H/I's pinned-version read contract.

Updating the single detail to v2 would make S1 fail. Retaining v1 makes S2 fail. Overriding either snapshot pin, weakening H/I's version validation, creating renamed duplicate items, or downgrading the analysis to scenario-only would bypass the requirement. None was implemented.

The current M2-A composition's scenario-level plan does not exercise this DataItem read. It is not evidence that M2-B's real document-derived formal inventory is reproducible. Exact document-universe filtering also remains unfinished and cannot by itself resolve the single-row detail identity conflict.

## Minimum resolution options for owning review

1. **Preferred:** approve an additive version-addressable extension of the existing DataItem context authority. Preserve canonical DataItem identity; retain immutable detail per inventory version and scope provenance/membership to the existing context run and snapshot document/parse pins. E writes, and F/H/I adapters read, the same exact version. Legal engines and workflow authority remain unchanged. This requires coordinated persistence/port and migration ownership review, not a node workaround.
2. Approve an explicit immutable formal-item version identity contract within the existing canonical DataItem store, with reviewed deduplication and historical-read semantics across E/F/H/I. Do not invent version suffixes or clone formal IDs without that decision.

Neither option has been implemented. Resume only after the contract decision, then add successful S1/S2 isolation tests, finish exact-input integration/UI, and run the complete M2-B closure. No frontend or frozen legal-owner file was changed to bypass this blocker.

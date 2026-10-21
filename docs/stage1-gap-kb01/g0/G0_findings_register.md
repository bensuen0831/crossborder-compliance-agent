# G0 findings register

AI independent-pass / **second-pass review**, not a designated human or third-party approval. Review date 2026-10-21T03:27:46.611373+00:00. Product source `39c3581ca455df4e3ce9760ed2deab8905a5f588`; main `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`; prior independently archived acceptance commit `bd30290c577e8ac16cbb88a20a0535553fb6bd00`. These are three different identities. No product source, test assertion, frozen migration or release tag was changed for this review. PR29 remains Draft. No merge or Stage2 is authorized.

Code references below resolve against [the reviewed product tree](https://github.com/bensuen0831/crossborder-compliance-agent/tree/39c3581ca455df4e3ce9760ed2deab8905a5f588); the original complete acceptance package is [separate evidence](https://github.com/bensuen0831/crossborder-compliance-agent/tree/bd30290c577e8ac16cbb88a20a0535553fb6bd00).

Critical0 OPEN; High0 OPEN; Medium2 OPEN. No product fix was performed. Open Medium findings have a documented non-blocking technical-scope assessment, requiring formal reviewer evaluation; this is not a risk approval or a claim they were fixed.

## KB01-G0-001 — Medium

**Source File**: `src/crossborder_compliance/infrastructure/persistence/knowledge_taxonomy.py`

**Line**: 242

**Related Lines**: [251, 260, 388]

**Affected Contract**: Bounded taxonomy-list query scalability; SQL statistics aggregates are a separate fixed-query path.

**Reproduction**: Create four synthetic canonical taxonomy rows. Instrument the real SQLAlchemy engine; call list(page_size=1), then list(page_size=4) under the same tenant/read grant. See review_probes.py.

**Actual Result**: {'1': 5, '4': 14}

**Expected Result**: Batch selected-version and actor projections so query count does not grow linearly with page size.

**Impact**: Three per-row reads add network/database latency. Page size is capped at 100; no cross-tenant leak, wrong count or measured acceptance timeout resulted.

**Recommended Fix**: In a separately validated change, load selected versions and creator/latest actor projections with bounded batch queries; preserve payload, tenant scope and stable order.

**Regression Test**: test_taxonomy_list_query_growth_is_measured reproduces 5 vs 14 statements; future regression should assert constant bounded query count and unchanged response semantics.

**Resolution**: `OPEN_NON_BLOCKING_FOR_FORMAL_REVIEW`

**Merge Blocking Assessment**: No stated latency SLA is violated in measurements; bounded administrative list, not a correctness/security failure. Formal reviewer must assess this deferral.

**Product Fix Performed**: False

## KB01-G0-002 — Medium

**Source File**: `scripts/kb01/Containerfile`

**Line**: 2

**Related Lines**: [7]

**Affected Contract**: Reconstruction of historical native-tool binary environment from Git alone.

**Reproduction**: Inspect FROM debian:trixie-slim and unversioned apt-get install package names; rebuild with the repository helper and record the newly produced immutable image ID.

**Actual Result**: {'base_tag_is_mutable': True, 'apt_package_versions_are_not_frozen': True, 'current_review_image': 'sha256:15fbf1cb1c8349e018de488f31ec4ae366b6ecebbbced32934d0127644d787ac'}

**Expected Result**: A release reproducibility policy should pin a reviewed base digest and package snapshot or retain an independently identified image/SBOM.

**Impact**: Git/source digest alone cannot reconstruct the identical historical tool image; package updates can alter later parser/scanner behavior. Existing executed image IDs, source hashes, signed Debian installation and CVD signature verification remain valid traceability evidence. No compromised package is alleged.

**Recommended Fix**: Define an approved immutable image retention and patch-refresh policy; pin reviewed base/package provenance and record SBOM/tool versions before production acceptance. Revalidate any resulting source/image change.

**Regression Test**: Actual bounded sandbox probe passes; build helper records image/source digests. A future reproducibility gate should verify approved image/package provenance.

**Resolution**: `OPEN_NON_BLOCKING_FOR_L1_TECHNICAL_FORMAL_REVIEW`

**Merge Blocking Assessment**: Each technical run uses a concrete sha256 image and signed tool installation. Production deployment remains explicitly NOT ACCEPTED; no change is made solely to manufacture a clean findings register. Formal reviewer must assess the residual risk.

**Product Fix Performed**: False

External review limitations: no designated formal reviewer has approved PR29; legacy protection details403 despite readable main endpoint reporting unprotected and no applicable readable rules; original complete historical MASTER attachment unavailable in this session. These are disclosed review/authorization dependencies, not fabricated successful gates. F1, deployment, UAT and paid-provider boundaries are retained independently.

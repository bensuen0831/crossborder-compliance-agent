# Stage 1 Full Business E2E — D0 inventory

## Source identity and scope

Branch: `milestone-stage1-full-e2e`, created directly from verified main
`df3a10923734495d728981f4f319b66afadf8c71`.
Annotated baseline tag: `v3.7-m2e-pass`; tag object
`c92daef5b47136fb14e2782c737927176d45086a`; dereference: the same main SHA.
Single Alembic head: `0018_phase1h_multijurisdiction_classification_identity`.
Start gate: PASS. No product, test, migration, workflow or specification change
was made before this inventory. The pre-existing untracked
`Phase1H_integration_closure.md` is preserved, SHA-256
`c9530e2a9c36746deadc143e3e94ab982c370650b653758ebe2f1d1aeb19ec37`.

The checked-in V3.7 Master Specification, Phase0 design, consistency/change
summary and `ARCHITECTURE_RULES.md` were read before implementation. The first
two supplied specification files end at approximately line 1000; their absent
continuation cannot be claimed as reviewed. M2-A/B/C/D, Phase1K-B and M2-E
handoffs and the relevant fixture/owner contracts were inspected. No
specification rewrite is proposed.

`docs/m2e/M2E_main_integration_closure.md` is intentionally absent from product
main. Its authoritative copy was read from independent evidence commit
`c6cb5f1a723af0965c2204a41f7392efc4140ebe`, branch
`evidence/m2e-main-closure-df3a109`. PR-unmerged wording in the older M2-E
handoff is historical, not the current source identity.

Baseline counts (historical, not this new branch's measured closure): backend
910, architecture 307/307, runtime 25/25, frontend 135, browser 60/60,
retries 0. Paid Internet LLM: NOT EXECUTED.

## The fifteen inventory questions

1. **Closest blank-project Browser journey.**
   `frontend/e2e/m2c.spec.ts` creates a project through the real intake UI,
   enters structured facts, uploads genuine DOCX, parses, confirms, starts the
   canonical workflow and inspects structured result/evidence with reload.
   `frontend/e2e/phase1kb.spec.ts` adds governed model selection and actual
   loopback HTTP extraction. Neither is the required four-outcome journey.

2. **Already verified milestone slices.**
   M2-A: canonical Project/ProjectVersion draft, restore, CAS and confirmation.
   M2-B: actual binary upload, versioned document links, ParseRun/SourceTrace,
   immutable exact document/parse pins. M2-C: formal cross-border and required
   document authorities, result projection/workspace, all requirement levels.
   M2-D: canonical ReviewTask/append-only ReviewDecision, same-Snapshot owner
   resume, request-changes hold, typed fact-conflict successor and history.
   Phase1K-B: governed multi-provider selection, invocation policy, actual HTTP,
   redaction/audit, document candidates and scoped retrieval query expansion.
   M2-E: OAuth/scopes, async external transport, event/delivery security,
   OpenAPI/SDK, successor operation and R1 jurisdiction-scoped classification.
   These are capabilities to reuse, not new acceptance evidence.

3. **Real PostgreSQL fixtures.**
   `test_phase1f_postgres.fixture`, `foundation_i` and `foundation_j`, reused
   through M2-A/B/C/D/E and Phase1K-B tests, operate on PostgreSQL via canonical
   repositories. Runtime smoke uses PostgreSQL durable checkpoints. Loopback
   UAT scripts use the same PostgreSQL fixture graph. Unit contract tests and
   frontend request mocks are not PostgreSQL business acceptance.

4. **Genuine DOCX fixtures.**
   `frontend/e2e/fixtures/m2c-intake.docx`, generated binary DOCX in
   `frontend/e2e/m2d.spec.ts`, and `docx()` in
   `tests/test_m2e_vertical_postgres.py` are genuine ZIP/XML DOCX. M2-B browser
   and Phase1K-B semantic document tests use genuine text files, not DOCX.
   New semantic-extraction coverage must use DOCX without native fields that
   would legitimately suppress semantic extraction.

5. **Seeded formal results.**
   `frontend/scripts/m1/uat.py:seed` calls foundation classification,
   applicability and retrieval before opening seeded contexts. M1/M0 pages
   therefore do not establish a blank-project end-to-end pipeline.
   M2-C and M2-D create new projects in the browser; foundations provision
   tenant configuration separately. New acceptance must never reuse their
   already computed foundation results as the new project's formal results.

6. **Real cross-border DataFlow.**
   M2-A/B/C/D and Phase1K-B browser forms select the same jurisdiction for
   source and destination. M2-E's HTTP vertical test uses distinct governed
   jurisdictions, but does not prove persisted DataFlowNode/Edge/ItemFlowLink.
   `frontend/src/features/intake/persistence.ts:draftFacts` explicitly omits
   draft `flows`; `IntakeFacts` has narrative `data_flow_description`, not a
   typed flow-binding selection. `prepare_snapshot` does not pass
   `data_item_flow_bindings` to `ContextResolutionService.run`. A narrative or
   two dropdown values must not be reported as the requested real flow.

7. **DOCX participation in formal inputs.**
   The native M2-E DOCX produces a governed `GENERIC_FIELD` BusinessFact and a
   table-header DataItem, with SourceTrace and snapshot parse pins. The native
   M2-C and M2-D cases also use document facts. This proves more than an
   attachment. It does not prove a DOCX-derived real source/destination flow.
   Phase1K-B's semantic tests prove source-addressed candidate facts and later
   canonical normalization, but not an intervening channel user confirmation.

8. **Full chain assertions.**
   C0/Phase1J contract and PostgreSQL tests cover classification, applicability,
   cross-border, obligation, candidate path, risk, recommendation, final path
   and required documents as separate owners. Existing M2-E vertical assertions
   cover completion, classification, final path, legal basis and evidence;
   they do not exhaustively assert every intermediate reference for all four
   outcomes. The new suite must add those assertions, not infer them from
   `COMPLETED` or a final path code.

9. **Real LLMInvocationPolicy fixtures.**
   `tests/test_phase1kb_selection_postgres.py:selected`,
   `tests/test_phase1kb_document_postgres.py:document_frame`, and
   `frontend/scripts/phase1kb/uat.py` publish provider/deployment, tenant/project
   ModelUsagePolicy, LLMInvocationPolicy and purpose-bound prompts through
   existing publication owners. `phase1kb_http_servers.local_provider` receives
   actual protocol HTTP requests. Document enhancement uses PinnedDocumentInput,
   not the selection fixture's unrelated FakeInputSource protocol smoke.

10. **Knowledge-gap HTTP query expansion.**
    `tests/test_phase1kb_query_postgres.py` exercises real local HTTP after a
    retrieval miss, a second search inside the same pinned scope, exclusion of
    unrelated product knowledge, candidate-only expansion manifest and
    authoritative/insufficient outcomes. The canonical workflow composition
    already installs `query_expansion_planner`. This is existing functionality;
    the missing coverage is a continuous new-project journey and recorded
    provenance/negative scope assertions.

11. **Current Web/API parity.**
    `tests/test_m2e_vertical_postgres.py` compares Web and External API adapters
    over the *same* authorized project/context/result. It does not create two
    independent projects from a shared manifest, normalize volatile identity,
    or compare all four formal outcomes. M2-E browser tests are Integration
    Center administration, not a blank-project external business journey.

12. **Blank-project review.**
    `frontend/e2e/m2d.spec.ts:createReview` does create a blank project. It covers
    approval, request changes and a DOCX-versus-manual fact conflict in each
    locale. Its configured requirement confirmation is not evidence of a
    cross-border legal status, and it currently uses identical jurisdictions.

13. **Channel successor coverage.**
    M2-D Browser submits a typed canonical fact-conflict selection and verifies
    successor Snapshot/run/result with old result unchanged. M2-E HTTP invokes
    `intake/supersede`, updates and confirms a successor, and rereads old output.
    The new suite still needs successor execution to a complete new result and
    future knowledge/rule/model publications with exact historical replay.

14. **Product omissions versus acceptance omissions.**
    Acceptance omissions include the 4x3 matrix, separate-project parity,
    comprehensive chain/provenance assertions, SDK business smoke, fresh-case
    observability and a dedicated workflow. Two product integration omissions
    need D0 diagnosis before claiming acceptance-only work: (a) typed flow
    candidate/jurisdiction/item binding is not carried by production intake;
    (b) real semantic extraction is invoked inside confirmation, and generated
    eligible facts are immediately normalized, without a candidate-preview
    confirmation boundary. `PinnedDocumentInput.load` requires CONFIRMED or
    SUPERSEDED ProjectVersion and exact AnalysisSnapshot/ParseRun pins. Draft
    catalog model eligibility is not a pinned invocation authorization.
    The finite M2-E owner proof also rejects every new test/workflow/rule path;
    an additive acceptance scope must preserve its existing owner hashes and
    all checks, not bypass them or self-certify modified production owners.

15. **Schema/migration/new feature decision.**
    No new migration is authorized or proposed. Existing DataFlow entities and
    services already exist; their unwired channel inputs do not alone prove a
    need for a new table. However, the requested pre-confirmation LLM candidate
    journey has no existing durable, pinned draft-invocation authorization
    identity/transition. Diagnose the existing real boundary before choosing
    between an explicit extension of the owning input/configuration contract
    and a newly approved preview identity. Never create a synthetic confirmed
    Snapshot, use draft catalog mode to evade pinning, mutate historical input,
    or substitute fixture candidates for actual gateway extraction.

## D0 execution decision

Inventory complete. A bounded, unchanged-source PostgreSQL/HTTP/DOCX diagnostic
confirmed the missing candidate-confirmation boundary. Draft parsing produced
no semantic invocation; confirmation then invoked the local HTTP provider and
immediately persisted a VALIDATED formal BusinessFact with an ACCEPTED/POLICY
candidate resolution. There was no subsequent user action to confirm the new
candidate. The existing input adapter rejects non-confirmed ProjectVersion and
requires exact AnalysisSnapshot/parse pins. A preview requires a canonical
pre-confirmation authorization/configuration identity decision, not a test
helper that fabricates a confirmed snapshot or disables pinning.

**HIGH_REASONING_ESCALATION_REQUIRED — STAGE1 FULL E2E = BLOCKED**.
Reason: `PRECONFIRMATION_CANDIDATE_AUTHORIZATION_CONTRACT_MISSING`.
Apply the user's section 103 stop rule before any product modification. The
required migration, if any, has **not** been established; no 0019 is proposed.
See `Stage1_E2E_test_result.md` and the machine-readable counterexample under
`evidence/stage1-full-e2e/`. No four-outcome, browser, dedicated CI or PR closure
result is claimed by this inventory.

Retained boundaries remain explicit: multi-subject workflow not configured;
historical formal result authority not configured; unsupported correction
targets (including flow correction); legacy read-only authority; no partial
rerun optimizer. Stage 2 remains NOT STARTED.

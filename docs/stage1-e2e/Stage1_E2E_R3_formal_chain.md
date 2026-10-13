# Stage1 E2E R3 — formal chain

`stage1_formal_acceptance.assert_formal_chain` checks persisted formal owners, dependency foreign keys and exact upstream support unions. All twelve LegalSupport fields remain in semantic parity. Only existing authorized references may propagate; fields are not required to be nonempty when the source contract legitimately supplies none. Classification, applicability and legal transfer status remain independent of path feasibility. RequiredDocument never enables generation.

R2 algorithms and persisted version checks remain byte-identical to 292fc6e9. V2 is historical read/verify only; new complete chains use V2_1. Full digest, input/pin authorization, version agreement and mixed-chain guards are retained.

Final exact-head measurements: PASS on `25b2cb34be24578c74ea7ed4931f9534ff0289f3`; see `Stage1_E2E_R3_test_result.md` and the adjacent R3 evidence files. Only L1 synthetic governed acceptance is covered.

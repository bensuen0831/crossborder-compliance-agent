# Sufficiency UI result

KnowledgeSufficiencyResult.status is rendered exactly as one of SUFFICIENT,
PARTIALLY_SUFFICIENT, INSUFFICIENT, CONFLICTED, with text and color. The UI displays backend
evidence counts, missing topics, reason codes, jurisdiction coverage and policy version. It does
not calculate sufficiency from result count or similarity.

FallbackPanel presents the existing ActionableFallbackGuidanceContext: acquisition, jurisdiction
verification, operational and conservative actions, unresolved questions and prohibited
assertions. Human-readable translations describe existing action codes, which remain visible.
Unknown codes retain their backend value. The panel explicitly states these are evidence
acquisition actions, not Final Compliance Path. No verified obligation, risk score, legal answer,
classification or cross-border conclusion is fabricated.

Real browser UAT demonstrated INSUFFICIENT with nonempty fallback both with evidence and with
a no-match query. Unit rendering covers all four possible statuses using explicitly test-only
fixtures; it does not claim a live sufficient/conflicted production case was executed.

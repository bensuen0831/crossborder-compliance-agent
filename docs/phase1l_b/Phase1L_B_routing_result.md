# Phase1L-B routing and guards

Existing StageOutcomeCode remains canonical. Formal COMPLETED/ordinary success maps to SUCCESS; existing EVIDENCE_INSUFFICIENT carries the formal INSUFFICIENT_EVIDENCE outcome and a persisted evidence-pack fallback ref. CONFLICTED precedes insufficiency, then REVIEW_REQUIRED. NOT_APPLICABLE, INSUFFICIENT_INPUT, CAPABILITY_NOT_CONFIGURED, LOW_CONFIDENCE and explicit technical outcomes retain existing L-A routing. Unknown future formal status fails closed. No routes parse narrative text.

Ties/prohibitions/unavailable candidates cannot fabricate a final path. The owning J service preserves legal viability independently of risk/availability. Conditional proposals retain obligations/unmet conditions and unperformed actions. Graph nodes return UUID refs and stable reason codes, not legal payloads.

Keep bounded node retries, max attempts/backoff, recursion limit, step/visit guards and post-call timeout rejection. Business/review/capability/evidence outcomes are never transient retries. Queue contention is separately retryable. Synchronous owning-service cancellation/deadline preemption remains unavailable; late results can already have persisted idempotent effects, and a timeout does not prove cancellation. The existing runtime cancel boundary remains unchanged.

preferred_locale exists only in RuntimeContext. zh-CN/zh-HK/en-US read projections and duplicate deliveries leave completed stages, snapshot pins, digests and checkpoint IDs unchanged. Official source-language filtering remains a fixed owning query/policy choice.

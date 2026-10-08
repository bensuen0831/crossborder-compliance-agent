# Invocation policy contract

`LLMInvocationPolicy` is an immutable governed MetadataVersion payload, not ModelUsagePolicy. It maps usage modes to allowed stable triggers and limits multi-model fanout. The owning input/retrieval service produces trigger facts; browser booleans are not accepted as authority.

Complete structured fields require no semantic re-extraction. Evidence-sufficient retrieval cannot trigger query expansion. MINIMAL accepts only parser insufficiency/ambiguity triggers; STANDARD additionally permits insufficient-retrieval expansion and explicit derived explanation. ENHANCED permits governed multi-model candidate/derived work. Published policy may further restrict every mode. Stage2 triggers are declared for compatibility and always denied in this phase. Legal-decision purposes are absent from the accepted purpose enum.

Invocation decision is independent of provider eligibility. An allowed trigger still requires current authorization, exact snapshot/policy/prompt/model versions, health/capabilities, tenant/project usage-policy intersection, trusted resource loading, redaction where required and a durable audit sink.

# M1 backend contract gaps

| Code / capability | Owner | Affected UI / safe behavior |
|---|---|---|
| M1_WORKFLOW_INTEGRATION_PENDING_PHASE1L_B — unified analysis execution on the Phase1J base | Phase1L-B integration owner | Execute disabled; existing independent formal results remain readable; no substitute browser workflow |
| M1_BACKEND_CONTRACT_GAP — ProjectIntakeContext persistence/project creation API | Project/intake API owner + verified workflow integration | Ephemeral facts only; confirmation explicitly does not submit or update formal context |
| M1_BACKEND_CONTRACT_GAP — production binary upload/document-intake linkage | M1 Document integration + production storage/security | Upload disabled; current authorized document summary readable, draft references unverified |
| M1_BACKEND_CONTRACT_GAP — governed data-category options distinct from data types | Metadata/data inventory owner | Category selection unavailable; data types remain separate governed inputs |
| M1_BACKEND_CONTRACT_GAP — scenario description localization and availability contract | Scenario metadata/capability owner | Existing canonical description/fallback or unavailable message; no scenario dictionaries/LLM translation |
| M1_BACKEND_CONTRACT_GAP — snapshot-scoped formal-context/data-flow read projection | Phase1E context API owner | Current project views explicitly labelled; formal result identity independently checked |
| M1_BACKEND_CONTRACT_GAP — classification/applicability result discovery/list and legal-basis detail API | Phase1H/I read API owners | Authorized known reference IDs and actual legal-basis identities only; no fabricated lists/details |
| Existing production identity/CSRF and fine-grained RBAC | Production/security owners | Existing trusted host boundary remains; synthetic loopback sessions are UAT only; backend authorization authoritative |

Phase1I solved localized governed metadata presentation. M1 consumes it directly; Stage1-alpha's older metadata gap is not treated as a permanent missing capability. No Phase1L-B implementation or backend migration is introduced.

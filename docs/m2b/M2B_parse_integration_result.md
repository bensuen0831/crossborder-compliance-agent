# M2B parse integration result

Existing DocumentParseService/native parsers, durable document_parse_tasks and genuine SourceTrace are reused. Task acceptance commits before execution. Atomic parse persistence prevents partial runs/candidates/traces; repeated delivery is serialized. Empirical subprocess crash after acceptance leaves ACCEPTED and authorized restart creates one completed run. Unknown candidate fact types remain unformalized and route durable review through existing context/workflow authority.

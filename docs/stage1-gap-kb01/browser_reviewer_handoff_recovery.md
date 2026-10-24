# Canonical browser reviewer handoff recovery

The prior head `282f97a6ce00c1462a23c41f910dea5a7adb4a19` completed 11/12 workflows successfully. M2-E run38927685806, frontend job117063319492, had23 browser passes and one failure: the zh-HK Phase1K-B model reviewer POST expected200 and received409. The workflow-level monitor originally missed this failed job while its backend job was still running; the collector now checks each job as well as workflow conclusions.

Real PostgreSQL, HTTP, Chromium and the unchanged canonical local provider reproduce the race: a Submit click dispatches an asynchronous transition, while the test immediately reads a stale deployment version. With500ms forwarded-request latency, early approval returns422 while the deployment is stillDRAFT1; retaining that read until Submit commits reproduces409 againstPENDING_REVIEW2. These failed diagnostic probes are preserved, not counted as acceptance passes.

The test now awaits the exact committed Submit response before reviewer handoff, selects the created deployment by identity, and checks its lifecycle and version against that response. Provider Submit and both Publish operations use the same committed-response ordering. The500ms latency fixture forwards the real request unchanged. The private1500ms reproduction wait is removed. No product owner, CAS, actor separation, approval assertion, coverage, browser retry or timeout changes.

An initial helper-authoring probe incorrectly waited forPUBLISHED instead of the canonicalACTIVE publish target; its three response-wait failures are retained privately and the helper now uses the actual production API contract. They are not acceptance evidence.

All final mandatory workflows must rerun on the newly sealed source. Previous11/12 evidence cannot close the successor. Main and release tag remain unchanged; PR29 remainsDraft. F1 remainsBLOCKED—EXTERNAL_EVIDENCE_PENDING. Stage2 remainsNOT STARTED.

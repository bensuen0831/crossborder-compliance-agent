# Browser UAT

Final tested main: `83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1`. Integrated PR20 source: `a753aa12150e1c81456f18ed3c0d5d53b2fc58ea`. Annotated tag `v3.6-m1-phase1lb-pass` (object `f24c40923daca096145504b449f99e861fce66d7`), target `83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1`. Migration head `0010_phase1j`.

Exact-main M1 CI37425898441:3/3 locale tests passed,0 skipped/unexpected/flaky,0 retries. All four personas use actual PG/LangGraph canonical workflow. Covers backend run/ref identity, official evidence, language persistence without extra START, context/tenant clearing and denial, partial evidence WARNING/fallback, pending reviews without approval, context conflict. Separate M0 CI37425901297:36/36 browser regression (three repetitions),0 skipped/unexpected/flaky/retries. Local uses PG17/Redis8/system Chromium; remote isolated CI uses PG16/Redis7/Playwright Chromium. Browser personas use synthetic loopback sessions, not production auth.

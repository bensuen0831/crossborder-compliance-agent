# Phase 1A.1 Test Result

**Decision: PASS**

~~~text
........................................................................ [ 26%]
........................................................................ [ 52%]
........................................................................ [ 78%]
............................................................             [100%]
=============================== warnings summary ===============================
tests/test_phase1c_admin_api.py::test_model_admin_response_never_returns_secret_and_unsafe_url_rejected
  /workspace/phase1k-llm-gateway-foundation/src/crossborder_compliance/interfaces/api/routes/admin_metadata.py:171: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    _translate_error(exc)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
--- generated xml file: /workspace/phase1k_a_gate4_evidence/pytest_full.xml ----
276 passed, 1 warning in 42.83s
~~~

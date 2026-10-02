# Phase 1A.1 Test Result

**Decision: PASS**

~~~text
........................................................................ [ 36%]
........................................................................ [ 72%]
........................................................                 [100%]
=============================== warnings summary ===============================
tests/test_phase1c_admin_api.py::test_model_admin_response_never_returns_secret_and_unsafe_url_rejected
  /workspace/crossborder-compliance-agent/src/crossborder_compliance/interfaces/api/routes/admin_metadata.py:171: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    _translate_error(exc)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
---- generated xml file: /workspace/phase1g_gate4_evidence/pytest_full.xml -----
200 passed, 1 warning in 34.04s
~~~

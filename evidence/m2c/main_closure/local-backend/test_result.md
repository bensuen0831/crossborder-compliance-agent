# Phase 1A.1 Test Result

**Decision: PASS**

~~~text
........................................................................ [  9%]
........................................................................ [ 19%]
........................................................................ [ 29%]
........................................................................ [ 39%]
........................................................................ [ 49%]
........................................................................ [ 59%]
........................................................................ [ 69%]
........................................................................ [ 79%]
........................................................................ [ 89%]
........................................................................ [ 99%]
.......                                                                  [100%]
=============================== warnings summary ===============================
../compliance-env/lib/python3.12/site-packages/alembic/config.py:604
../compliance-env/lib/python3.12/site-packages/alembic/config.py:604
  /workspace/compliance-env/lib/python3.12/site-packages/alembic/config.py:604: DeprecationWarning: No path_separator found in configuration; falling back to legacy splitting on spaces, commas, and colons for prepend_sys_path.  Consider adding path_separator=os to Alembic config.
    util.warn_deprecated(

tests/test_m2a_migrations.py::test_m2a_fresh_exact_0010_equivalence_downgrade_and_refusal
tests/test_m2b_migrations.py::test_fresh_exact_0011_equivalence_empty_down_up_and_retention
tests/test_m2c_migrations.py::test_fresh_exact_0013_equivalence_empty_down_up_retention
tests/test_phase1h_migrations.py::test_fresh_and_frozen_0007_paths_equivalent_and_downgrade
tests/test_phase1i_migrations.py::test_phase1i_fresh_verified_0008_equivalence_and_downgrade
tests/test_phase1j_migrations.py::test_phase1j_fresh_exact_0009_schema_equivalence_and_downgrade
  /workspace/crossborder-compliance-agent/tests/test_phase1h_migrations.py:45: SAWarning: Did not recognize type 'vector' of column 'embedding_vector'
    for c in inspector.get_columns(table)

tests/test_phase1c_admin_api.py::test_model_admin_response_never_returns_secret_and_unsafe_url_rejected
  /workspace/crossborder-compliance-agent/src/crossborder_compliance/interfaces/api/routes/admin_metadata.py:189: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    _translate_error(exc)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
- generated xml file: /workspace/m2c-main-control/local-backend/pytest_full.xml -
727 passed, 9 warnings in 1261.69s (0:21:01)
~~~

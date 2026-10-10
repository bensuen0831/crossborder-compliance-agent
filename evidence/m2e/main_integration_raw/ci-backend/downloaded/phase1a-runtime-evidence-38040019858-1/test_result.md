# Phase 1A.1 Test Result

**Decision: PASS**

~~~text
........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
........................................................................ [ 31%]
........................................................................ [ 39%]
........................................................................ [ 47%]
........................................................................ [ 55%]
........................................................................ [ 63%]
........................................................................ [ 71%]
........................................................................ [ 79%]
........................................................................ [ 87%]
........................................................................ [ 94%]
..............................................                           [100%]
=============================== warnings summary ===============================
../../../../../opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/alembic/config.py:604
../../../../../opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/alembic/config.py:604
  /opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/alembic/config.py:604: DeprecationWarning: No path_separator found in configuration; falling back to legacy splitting on spaces, commas, and colons for prepend_sys_path.  Consider adding path_separator=os to Alembic config.
    util.warn_deprecated(

tests/test_m2a_migrations.py: 1 warning
tests/test_m2b_migrations.py: 1 warning
tests/test_m2c_migrations.py: 1 warning
tests/test_m2d_migrations.py: 1 warning
tests/test_m2e_integration_migrations.py: 1 warning
tests/test_m2e_r11_migrations.py: 1 warning
tests/test_phase1h_migrations.py: 1 warning
tests/test_phase1i_migrations.py: 1 warning
tests/test_phase1j_migrations.py: 1 warning
tests/test_phase1kb_migrations.py: 1 warning
  /home/runner/work/crossborder-compliance-agent/crossborder-compliance-agent/tests/test_phase1h_migrations.py:45: SAWarning: Did not recognize type 'vector' of column 'embedding_vector'
    for c in inspector.get_columns(table)

tests/test_m2e_integration_migrations.py::test_empty_and_populated_integration_downgrade_transactional_policy
tests/test_m2e_integration_migrations.py::test_empty_and_populated_integration_downgrade_transactional_policy
tests/test_m2e_integration_migrations.py::test_empty_and_populated_integration_downgrade_transactional_policy
  /home/runner/work/crossborder-compliance-agent/crossborder-compliance-agent/tests/test_m2e_integration_migrations.py:67: SADeprecationWarning: The Result.tuples() method is deprecated, Row now behaves like a tuple and can unpack types directly. (deprecated since: 2.1.0)
    ).tuples()

tests/test_phase1c_admin_api.py::test_model_admin_response_never_returns_secret_and_unsafe_url_rejected
  /home/runner/work/crossborder-compliance-agent/crossborder-compliance-agent/src/crossborder_compliance/interfaces/api/routes/admin_metadata.py:195: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    _translate_error(exc)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
- generated xml file: /home/runner/work/crossborder-compliance-agent/crossborder-compliance-agent/artifacts/phase1a-runtime/pytest_full.xml -
910 passed, 16 warnings in 1264.50s (0:21:04)
~~~

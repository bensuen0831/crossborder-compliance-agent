# Phase 1A.1 Test Result

**Decision: PASS**

~~~text
........................................................................ [  8%]
........................................................................ [ 17%]
........................................................................ [ 25%]
........................................................................ [ 34%]
........................................................................ [ 42%]
........................................................................ [ 51%]
........................................................................ [ 59%]
........................................................................ [ 68%]
........................................................................ [ 76%]
........................................................................ [ 85%]
........................................................................ [ 93%]
....................................................                     [100%]
=============================== warnings summary ===============================
../../../../../opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/alembic/config.py:604
../../../../../opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/alembic/config.py:604
  /opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/alembic/config.py:604: DeprecationWarning: No path_separator found in configuration; falling back to legacy splitting on spaces, commas, and colons for prepend_sys_path.  Consider adding path_separator=os to Alembic config.
    util.warn_deprecated(

tests/test_m2a_migrations.py::test_m2a_fresh_exact_0010_equivalence_downgrade_and_refusal
tests/test_m2b_migrations.py::test_fresh_exact_0011_equivalence_empty_down_up_and_retention
tests/test_m2c_migrations.py::test_fresh_exact_0013_equivalence_empty_down_up_retention
tests/test_m2d_migrations.py::test_fresh_exact_0014_equivalence_empty_down_up_retention
tests/test_phase1h_migrations.py::test_fresh_and_frozen_0007_paths_equivalent_and_downgrade
tests/test_phase1i_migrations.py::test_phase1i_fresh_verified_0008_equivalence_and_downgrade
tests/test_phase1j_migrations.py::test_phase1j_fresh_exact_0009_schema_equivalence_and_downgrade
tests/test_phase1kb_migrations.py::test_fresh_exact0015_equivalence_empty_downgrade_reupgrade_and_retention
  /home/runner/work/crossborder-compliance-agent/crossborder-compliance-agent/tests/test_phase1h_migrations.py:45: SAWarning: Did not recognize type 'vector' of column 'embedding_vector'
    for c in inspector.get_columns(table)

tests/test_phase1c_admin_api.py::test_model_admin_response_never_returns_secret_and_unsafe_url_rejected
  /home/runner/work/crossborder-compliance-agent/crossborder-compliance-agent/src/crossborder_compliance/interfaces/api/routes/admin_metadata.py:195: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    _translate_error(exc)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
- generated xml file: /home/runner/work/crossborder-compliance-agent/crossborder-compliance-agent/artifacts/phase1a-runtime/pytest_full.xml -
844 passed, 11 warnings in 1432.88s (0:23:52)
~~~

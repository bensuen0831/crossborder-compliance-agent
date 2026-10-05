# Migration integration result

PASS on exact final main `594be84cfc471af4c12f28600b22cffb66f830f7`. Single head0009_phase1i; canonical Alembic tree byte-identical to reviewed Phase1I source14cba25353d9ab7dda84e9620ff3197d9e2a3d1d. Historical0001–0008 are byte-identical to verified Phase1H main. No parallel migration or renumbering.

{
  "baseline": "700951ebb9ebdf33e399158fd3fb53bb4a6c87e7",
  "baseline_revision": "0008_phase1h",
  "head": "0009_phase1i",
  "fresh_upgrade": true,
  "verified_0008_upgrade": true,
  "schema_equivalence": true,
  "empty_downgrade_roundtrip": true,
  "authoritative_downgrade_refused": true
}

Actual schema gates: {
  "phase1d_schema_check": {
    "passed": 15,
    "total": 15
  },
  "phase1f_schema_check": {
    "passed": 29,
    "total": 29
  },
  "phase1b_schema_check": {
    "passed": 16,
    "total": 16
  },
  "phase1e_schema_check": {
    "passed": 22,
    "total": 22
  },
  "phase1c_schema_check": {
    "passed": 20,
    "total": 20
  },
  "phase1i_schema_check": {
    "passed": 24,
    "total": 24
  },
  "phase1h_schema_check": {
    "passed": 20,
    "total": 20
  },
  "phase1g_schema_check": {
    "passed": 58,
    "total": 58
  }
}

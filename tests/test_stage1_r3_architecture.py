from pathlib import Path
from scripts.stage1_business_architecture import check

def test_additive_stage1_acceptance_contracts_preserve_frozen_owners():
    checks=check(Path(__file__).resolve().parents[1])
    assert len(checks)>=20 and all(checks.values()),[k for k,v in checks.items() if not v]

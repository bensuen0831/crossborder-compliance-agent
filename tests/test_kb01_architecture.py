from pathlib import Path

from scripts.kb01_architecture_check import check


def test_kb01_additive_architecture_contracts():
    results = check(Path(__file__).resolve().parents[1])
    assert len(results) == 81
    assert all(results.values()), [key for key, passed in results.items() if not passed]

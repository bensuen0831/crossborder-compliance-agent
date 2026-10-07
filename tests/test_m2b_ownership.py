"""Finite temporal/upload owner proof preserves all prior sources and ancestry."""
from pathlib import Path
from scripts import m2b_ownership as ownership


def test_m2b_owner_is_committed_finite_and_excludes_legal_engines():
    valid, paths, source = ownership.overlay(Path(__file__).resolve().parents[1])
    assert valid and paths and source
    assert paths.keys() == ownership.SHARED
    assert not any(p.startswith(('src/crossborder_compliance/domain/','src/crossborder_compliance/workflows/')) for p in paths)


def test_m2b_owner_cannot_approve_arbitrary_source(monkeypatch):
    original = ownership.json.loads
    def forged(raw):
        value = original(raw)
        if isinstance(value,dict) and 'source_sha' in value: value['source_sha'] = ownership.BASE
        return value
    monkeypatch.setattr(ownership.json,'loads',forged)
    assert not ownership.overlay(Path(__file__).resolve().parents[1])[0]

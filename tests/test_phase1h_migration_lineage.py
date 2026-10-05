
import pytest

from crossborder_compliance.infrastructure.persistence.migration_lineage import revision_at_or_after


@pytest.mark.parametrize(
    "phase",
    [
        "0002_phase1b",
        "0003_phase1c",
        "0004_phase1d",
        "0005_phase1e",
        "0006_phase1f",
        "0007_phase1g",
    ],
)
def test_real_phase_ancestry(phase):
    assert revision_at_or_after("0008_phase1h", phase)
    assert revision_at_or_after(phase, phase)


@pytest.mark.parametrize("current", [None, "head", "heads", "0008", "9999_future", "0001_phase1a"])
def test_unknown_alias_and_earlier_revisions_rejected(current):
    assert not revision_at_or_after(current, "0003_phase1c")


def graph(tmp_path, revisions):
    folder = tmp_path / "versions"
    folder.mkdir()
    for revision, parent in revisions:
        (folder / f"{revision}.py").write_text(f"revision={revision!r}\ndown_revision={parent!r}\n")
    return tmp_path


def test_parallel_heads_are_not_silently_accepted(tmp_path):
    location = graph(
        tmp_path, [("root", None), ("phase", "root"), ("track_a", "phase"), ("track_b", "phase")]
    )
    assert not revision_at_or_after("track_a", "phase", location)
    assert not revision_at_or_after("track_b", "phase", location)


def test_single_head_but_not_a_descendant(tmp_path):
    # A merge makes one head; a sibling is still not a descendant of the other branch.
    location = graph(
        tmp_path,
        [
            ("root", None),
            ("phase", "root"),
            ("parallel", "root"),
            ("merged", ("phase", "parallel")),
        ],
    )
    assert not revision_at_or_after("parallel", "phase", location)
    assert revision_at_or_after("merged", "phase", location)

"""Schema regression gates follow the repository's real, single Alembic lineage."""

from pathlib import Path

from alembic.script import ScriptDirectory
from alembic.script.revision import ResolutionError, RevisionError
from alembic.util.exc import CommandError


def revision_at_or_after(
    current: str | None, required: str, script_location: str | Path | None = None
) -> bool:
    """Reject unknown IDs, aliases, disconnected revisions and competing heads.

    A revision must be the required revision or descend from it in the checked-in
    graph. Multiple graph heads require a migration-ownership decision first.
    """
    if not current or not isinstance(current, str):
        return False
    location = script_location or Path(__file__).resolve().parents[4] / "alembic"
    try:
        graph = ScriptDirectory(str(location))
        if len(graph.get_heads()) != 1:
            return False
        now, phase = graph.get_revision(current), graph.get_revision(required)
        if now is None or phase is None or now.revision != current or phase.revision != required:
            return False
        if current == required:
            return True
        return any(
            revision.revision == current for revision in graph.iterate_revisions(current, required)
        )
    except (ResolutionError, RevisionError, CommandError, OSError, ValueError):
        return False

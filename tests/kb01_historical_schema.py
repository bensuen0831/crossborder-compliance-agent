"""Explicit historical bootstrap input for frozen0002's live-ORM DDL.

Current fresh0023 remains tested from the working source. Historical migration
tests must not accidentally bootstrap future columns from current ORM metadata.
No assertions, catalogs, test IDs or migration files are removed or weakened.
"""

import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "e012d2a35c68e1c1ad9ccec879d78e5a45ffc208"


def historical_bootstrap_source(directory, revision):
    directory = Path(directory)
    directory.mkdir()
    number = int(revision[:4])
    assert 19 <= number <= 22
    for path in (ROOT / "alembic/versions").glob("*.py"):
        if path.name[:4].isdigit() and int(path.name[:4]) <= number:
            assert path.read_bytes() == subprocess.check_output(
                ["git", "show", SOURCE + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            )
    archive = directory.parent / (directory.name + ".tar")
    with archive.open("wb") as output:
        subprocess.run(["git", "archive", SOURCE], cwd=ROOT, stdout=output, check=True)
    with tarfile.open(archive) as source:
        source.extractall(directory, filter="data")
    return directory

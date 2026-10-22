"""Index a copy of the mini fixture with two broken front matters."""

# error: ExceptionGroup: 2 files failed (2 sub-exceptions)

import contextlib
import shutil
import tempfile
from pathlib import Path

from sift.__main__ import load_index

MINI = Path("tests/fixtures/mini")


def break_front_matter(path: Path, old: str, new: str) -> None:
    """Replace the first old with new in the file at path."""
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    """Copy the fixture, break two files, then load the index."""
    source = MINI.resolve()
    with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):
        root = Path("mini")
        shutil.copytree(source, root)
        break_front_matter(root / "tea-brewing.md", "title:", "title: [")
        break_front_matter(root / "river-flow.md", "published:", "published")
        load_index(root)


if __name__ == "__main__":
    main()

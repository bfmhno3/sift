"""Reading the corpus: a lazy stream of raw Markdown documents."""

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple


class RawDoc(NamedTuple):
    """A Markdown file as read from disk, before any parsing."""

    path: Path
    text: str


def iter_documents(root: Path) -> Iterator[RawDoc]:
    """Yield every ``*.md`` file under root, one file at a time.

    Files come in sorted path order, so the position of a document in
    the stream is a stable doc_id. Each file is read when the consumer
    asks for it, never earlier.
    """
    for path in sorted(root.rglob("*.md")):
        yield RawDoc(path, path.read_text(encoding="utf-8"))

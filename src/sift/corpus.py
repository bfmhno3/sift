"""Reading the corpus: a lazy stream of parsed documents."""

import logging
from collections.abc import Iterator
from pathlib import Path

from sift.document import Document
from sift.errors import FrontMatterError

logger = logging.getLogger(__name__)


def iter_documents(
    root: Path, *, keep_going: bool = False
) -> Iterator[Document]:
    """Yield every ``*.md`` file under root as a Document.

    Files come in sorted path order and the doc_id of a document is
    its position in that order, also when a file before it failed.
    Each file is read and parsed when the consumer asks for it, never
    earlier.

    A file with a malformed front matter does not stop the stream.
    Its FrontMatterError is collected and the next file is read. When
    the files are exhausted, a non-empty collection is raised as one
    ``ExceptionGroup("3 files failed", [...])``. With keep_going the
    errors are logged as warnings (logger ``sift.corpus``) instead and
    nothing is raised. A consumer that stops early never sees the
    errors of the files it did not reach.
    """
    errors: list[FrontMatterError] = []
    for doc_id, path in enumerate(sorted(root.rglob("*.md"))):
        text = path.read_text(encoding="utf-8")
        try:
            doc = Document.from_markdown(doc_id, path, text)
        except FrontMatterError as error:
            errors.append(error)
            if keep_going:
                logger.warning("skipping %s", error)
            continue
        yield doc
    if errors and not keep_going:
        noun = "file" if len(errors) == 1 else "files"
        raise ExceptionGroup(f"{len(errors)} {noun} failed", errors)

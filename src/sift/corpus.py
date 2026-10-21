"""Reading the corpus: a lazy stream of parsed documents."""

from collections.abc import Iterator
from pathlib import Path

from sift.document import Document


def iter_documents(root: Path) -> Iterator[Document]:
    """Yield every ``*.md`` file under root as a Document.

    Files come in sorted path order and the doc_id of a document is
    its position in that order. Each file is read and parsed when the
    consumer asks for it, never earlier. A malformed front matter
    raises ValueError naming the file.
    """
    for doc_id, path in enumerate(sorted(root.rglob("*.md"))):
        text = path.read_text(encoding="utf-8")
        yield Document.from_markdown(doc_id, path, text)

"""Shared fixtures: the mini corpus, parsed and indexed once."""

from pathlib import Path

import pytest

from sift.corpus import iter_documents
from sift.document import Document
from sift.index import IndexWriter, InvertedIndex

MINI = Path(__file__).parent / "fixtures" / "mini"


@pytest.fixture(scope="session")
def mini_root() -> Path:
    """Return the directory of the eight fixture posts."""
    return MINI


@pytest.fixture(scope="session")
def mini_docs(mini_root: Path) -> list[Document]:
    """Return the fixture posts as Documents, doc_id 0 to 7."""
    return list(iter_documents(mini_root))


@pytest.fixture(scope="session")
def mini_index(mini_docs: list[Document]) -> InvertedIndex:
    """Return an index over the fixture posts.

    The scope is the session, so a test must only read it. A test that
    adds or removes documents builds its own InvertedIndex.
    """
    index = InvertedIndex()
    with IndexWriter(index) as writer:
        for doc in mini_docs:
            writer.add(doc)
    return index

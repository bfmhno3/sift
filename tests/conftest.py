"""Shared fixtures: the mini corpus, parsed and indexed once."""

import os
from pathlib import Path

# The Qt tests (and the doctests of sift.gui.qt) must never open a
# window: set the platform before anything imports PySide6. It is set,
# not defaulted: a desktop session exports "wayland" or "xcb" and
# setdefault would keep it.
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from sift.corpus import iter_documents
from sift.document import Document
from sift.index import IndexWriter, InvertedIndex
from sift.search import Searcher

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


@pytest.fixture
def searcher(mini_index: InvertedIndex) -> Searcher:
    """Return a Searcher over the fixture posts, new for every test."""
    return Searcher(mini_index)


# The window tests need a display: test_tk_window.py runs them under
# Xvfb, with this variable set.
if not os.environ.get("SIFT_TK_DISPLAY_TESTS"):
    collect_ignore_glob = ["tk_display/*"]

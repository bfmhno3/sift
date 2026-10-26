"""Shared fixtures: the mini corpus, parsed and indexed once."""

import importlib
import os
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

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
# The PyO3 module that sift.ext.rs imports: make ext-rs builds it.
RUST_MODULE = "sift._rs"


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


@pytest.fixture(scope="session")
def native() -> Callable[[str], ModuleType]:
    """Return a loader for the modules of sift.ext.

    The loader skips the test when the module is not built, that is
    when `make ext` or `make ext-rs` has not run. Any other import
    error is a failure.
    """

    def load(name: str) -> ModuleType:
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError as error:
            if error.name not in (name, RUST_MODULE):
                raise
        except OSError as error:
            if "No such file" not in str(error):
                raise
        pytest.skip(f"{name} is not built: run `make ext` and `make ext-rs`")

    return load


# The window tests need a display: test_tk_window.py runs them under
# Xvfb, with this variable set.
if not os.environ.get("SIFT_TK_DISPLAY_TESTS"):
    collect_ignore_glob = ["tk_display/*"]

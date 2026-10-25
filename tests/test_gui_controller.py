"""Tests for sift.gui.controller: no display, no tkinter."""

import threading
from collections.abc import Callable, Sequence

import pytest

from sift.errors import QuerySyntaxError, SiftError
from sift.gui.controller import (
    Controller,
    IndexBackend,
    Outcome,
    Preview,
    Row,
    start_thread,
)
from sift.search import Searcher


class FakeView:
    """A View that records what it is told."""

    def __init__(self) -> None:
        self.busy: list[bool] = []
        self.rows: Sequence[Row] = []
        self.selected: int | None = None
        self.statuses: list[tuple[str, bool]] = []
        self.preview: Preview | None = None

    def show_busy(self, busy: bool) -> None:
        self.busy.append(busy)

    def show_results(self, rows: Sequence[Row]) -> None:
        self.rows = rows

    def select_row(self, index: int | None) -> None:
        self.selected = index

    def show_status(self, text: str, *, error: bool) -> None:
        self.statuses.append((text, error))

    def show_preview(self, preview: Preview | None) -> None:
        self.preview = preview


def outcome(query: str, titles: list[str], took: float = 1.5) -> Outcome:
    rows = [Row(i, 10.0 - i, t, i) for i, t in enumerate(titles, start=1)]
    previews = [Preview(t, "meta", f"body of {t}", [(0, 4)]) for t in titles]
    return Outcome(query, len(titles), took, rows, previews)


class FakeBackend:
    """Answers from a dict; a missing key is a bad query."""

    def __init__(self, answers: dict[str, list[str]]) -> None:
        self.answers = answers
        self.calls: list[str] = []

    def search(self, query: str) -> Outcome:
        self.calls.append(query)
        if query == "boom":
            raise RuntimeError("bug")
        if query == "locked":
            raise SiftError("index busy")
        if query not in self.answers:
            raise QuerySyntaxError("expected a word", query, 1)
        return outcome(query, self.answers[query])


def inline(work: Callable[[], None]) -> None:
    work()


@pytest.fixture
def view() -> FakeView:
    return FakeView()


@pytest.fixture
def controller(view: FakeView) -> Controller:
    backend = FakeBackend({"rust": ["a", "b"], "none": []})
    return Controller(backend, view, spawn=inline)


def test_row_cells_and_outcome_status() -> None:
    row = Row(3, 1.0, "T", 9)
    assert row.cells() == ("3", "1.00", "T")
    assert outcome("q", ["a", "b"], 12.34).status() == "2 条结果，12.3 ms"


def test_preview_parts_cover_the_body() -> None:
    preview = Preview("t", "m", "ab cd ef", [(0, 2), (6, 8)])
    assert preview.parts() == [("ab", True), (" cd ", False), ("ef", True)]
    assert "".join(text for text, _ in preview.parts()) == "ab cd ef"
    assert Preview("t", "m", "", []).parts() == []


def test_blank_query_does_not_search(
    controller: Controller, view: FakeView
) -> None:
    assert controller.submit("   ") is False
    assert controller.pending == 0
    assert view.statuses == [("请输入查询", False)]
    assert view.busy == []


def test_submit_returns_before_the_answer_is_applied(
    controller: Controller, view: FakeView
) -> None:
    assert controller.submit(" rust ") is True
    assert controller.pending == 1
    assert view.busy == [True]
    assert view.statuses == [("搜索中…", False)]
    assert view.rows == []  # the answer waits in the queue


def test_poll_applies_the_answer(
    controller: Controller, view: FakeView
) -> None:
    controller.submit("rust")
    assert controller.poll() == 1
    assert controller.pending == 0
    assert [r.title for r in view.rows] == ["a", "b"]
    assert view.statuses[-1] == ("2 条结果，1.5 ms", False)
    assert view.selected == 0
    assert view.preview is not None and view.preview.title == "a"
    assert view.busy == [True, False]
    assert controller.poll() == 0


def test_select_shows_another_preview(
    controller: Controller, view: FakeView
) -> None:
    controller.submit("rust")
    controller.poll()
    controller.select(1)
    assert view.preview is not None and view.preview.title == "b"
    controller.select(5)  # out of range: unchanged
    assert view.preview.title == "b"
    controller.select(None)
    assert view.preview is None


def test_no_hits_empties_the_preview(
    controller: Controller, view: FakeView
) -> None:
    controller.submit("none")
    controller.poll()
    assert view.rows == []
    assert view.preview is None
    assert view.statuses[-1] == ("0 条结果，1.5 ms", False)


def test_syntax_error_shows_the_caret_message_as_an_error(
    controller: Controller, view: FakeView
) -> None:
    controller.submit("(oops")
    controller.poll()
    text, error = view.statuses[-1]
    assert error is True
    assert text == "expected a word\n  (oops\n   ^"
    assert view.rows == [] and view.preview is None


def test_other_errors_are_errors_too(
    controller: Controller, view: FakeView
) -> None:
    controller.submit("locked")
    controller.poll()
    assert view.statuses[-1] == ("error: index busy", True)
    controller.submit("boom")
    controller.poll()
    assert view.statuses[-1] == ("error: RuntimeError: bug", True)
    assert view.busy[-1] is False


def test_a_new_answer_clears_the_error(
    controller: Controller, view: FakeView
) -> None:
    controller.submit("(oops")
    controller.poll()
    controller.submit("rust")
    controller.poll()
    assert view.statuses[-1][1] is False


def test_only_the_newest_query_counts(view: FakeView) -> None:
    started: list[Callable[[], None]] = []
    backend = FakeBackend({"first": ["old"], "second": ["new"]})
    controller = Controller(backend, view, spawn=started.append)
    controller.submit("first")
    controller.submit("second")
    assert controller.pending == 2
    for work in started:
        work()
    assert controller.poll() == 2
    assert controller.pending == 0
    assert [r.title for r in view.rows] == ["new"]
    assert view.busy == [True, True, False]


def test_the_search_runs_on_another_thread(view: FakeView) -> None:
    seen: list[str] = []
    done = threading.Event()

    class Spy:
        def search(self, query: str) -> Outcome:
            seen.append(threading.current_thread().name)
            done.set()
            return outcome(query, ["x"])

    controller = Controller(Spy(), view, spawn=start_thread)
    controller.submit("q")
    assert done.wait(5)
    assert seen == ["sift-search"]
    assert threading.current_thread().name != "sift-search"
    for _ in range(500):
        if controller.poll():
            break
        done.wait(0.01)
    assert [r.title for r in view.rows] == ["x"]


def test_index_backend_builds_rows_and_highlighted_previews(
    searcher: Searcher,
) -> None:
    result = IndexBackend(searcher, limit=3).search("chain")
    assert result.query == "chain"
    assert result.total == 1
    (row,) = result.rows
    assert (row.rank, row.title) == (1, "Fixing a bicycle chain")
    (preview,) = result.previews
    assert preview.title == row.title
    assert preview.meta.startswith("20")
    marked = [text.lower() for text, hit in preview.parts() if hit]
    assert marked and set(marked) == {"chain"}
    assert "".join(t for t, _ in preview.parts()) == preview.body


def test_index_backend_limit_and_syntax_error(searcher: Searcher) -> None:
    backend = IndexBackend(searcher, limit=1)
    assert len(backend.search("tea OR bicycle").rows) == 1
    with pytest.raises(QuerySyntaxError):
        backend.search("(tea")

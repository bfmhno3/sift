"""What the search window does, without a single widget.

The window of ``sift.gui.tk_app`` is a ``View``: it draws rows, a
status line and a preview, and tells the ``Controller`` when the user
submits a query or selects a row. The controller starts the search on
a worker thread and hands the answer back through a ``queue.Queue``
that the window polls from the UI thread. Nothing here imports
tkinter, so the tests drive the controller with a fake view and a
fake backend and need no display.

The rules, in one place:

* A search never runs on the UI thread. ``submit`` starts a thread
  and returns at once.
* The worker only puts a message on the queue. It touches no view.
  ``poll`` runs on the UI thread and is the only code that calls the
  view with the answer.
* Only the newest query counts. An answer for an older one is dropped.
* A Sift error becomes a message for the status line, in the error
  style; a QuerySyntaxError keeps its caret line.
"""

import logging
import queue
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from sift.errors import QuerySyntaxError, SiftError
from sift.search import Searcher
from sift.snippet import highlight

log = logging.getLogger(__name__)

type Parts = list[tuple[str, bool]]


@dataclass(frozen=True, slots=True)
class Row:
    """One line of the result table."""

    rank: int
    score: float
    title: str
    doc_id: int

    def cells(self) -> tuple[str, str, str]:
        """Return the texts of the three columns.

        >>> Row(1, 2.5, "Rust", 7).cells()
        ('1', '2.50', 'Rust')
        """
        return str(self.rank), f"{self.score:.2f}", self.title


@dataclass(frozen=True, slots=True)
class Preview:
    """A document ready to show: heading, metadata, body, hit spans."""

    title: str
    meta: str
    body: str
    spans: list[tuple[int, int]]

    def parts(self) -> Parts:
        """Return the body as ``(text, is_hit)`` pieces, in order.

        >>> Preview("t", "m", "a fox ran", [(2, 5)]).parts()
        [('a ', False), ('fox', True), (' ran', False)]
        """
        parts: Parts = []
        cursor = 0
        for start, end in self.spans:
            if start > cursor:
                parts.append((self.body[cursor:start], False))
            parts.append((self.body[start:end], True))
            cursor = end
        if cursor < len(self.body):
            parts.append((self.body[cursor:], False))
        return parts


@dataclass(frozen=True, slots=True)
class Outcome:
    """The answer to one query: the table and a preview per row."""

    query: str
    total: int
    took_ms: float
    rows: list[Row]
    previews: list[Preview]

    def status(self) -> str:
        """Return the status line, ``N 条结果，X ms``."""
        return f"{self.total} 条结果，{self.took_ms:.1f} ms"


class Backend(Protocol):
    """Anything that answers a query; it runs on a worker thread."""

    def search(self, query: str) -> Outcome:
        """Return the outcome; raise SiftError for a bad query."""
        ...


class IndexBackend:
    """Search an open index with a Searcher, one query at a time.

    A Searcher is not thread-safe (its LRU cache), and a second query
    can start while the first still runs, so a lock serialises them.
    The previews are built here, on the worker thread, so that
    selecting a row costs nothing on the UI thread.
    """

    def __init__(self, searcher: Searcher, limit: int = 10) -> None:
        """Keep the searcher and the most rows to show."""
        self.searcher = searcher
        self.limit = limit
        self._lock = threading.Lock()

    def search(self, query: str) -> Outcome:
        """Search, then build the rows and the previews of the hits."""
        with self._lock:
            result = self.searcher.search(query, self.limit)
            terms = self.searcher.highlight_terms(query)
            documents = self.searcher.index.documents
            rows: list[Row] = []
            previews: list[Preview] = []
            for rank, hit in enumerate(result.hits, start=1):
                rows.append(Row(rank, hit.score, hit.title, hit.doc_id))
                doc = documents[hit.doc_id]
                body, spans = highlight(doc.body, terms)
                tags = ", ".join(doc.tags)
                meta = f"{doc.published:%Y-%m-%d}  {tags}".rstrip()
                previews.append(Preview(hit.title, meta, body, spans))
        return Outcome(
            result.query, result.total, result.took_ms, rows, previews
        )


class View(Protocol):
    """What the controller needs from a window."""

    def show_busy(self, busy: bool) -> None:
        """Show that a search runs (or has finished)."""
        ...

    def show_results(self, rows: Sequence[Row]) -> None:
        """Replace the table; no row is selected yet."""
        ...

    def select_row(self, index: int | None) -> None:
        """Select a row of the table, or none."""
        ...

    def show_status(self, text: str, *, error: bool) -> None:
        """Replace the status line; error picks the error style."""
        ...

    def show_preview(self, preview: Preview | None) -> None:
        """Replace the preview; None empties it."""
        ...


@dataclass(frozen=True, slots=True)
class Done:
    """Message of the worker: the search of request ``ident`` ended."""

    ident: int
    outcome: Outcome


@dataclass(frozen=True, slots=True)
class Failed:
    """Message of the worker: the search of ``ident`` failed."""

    ident: int
    text: str


@dataclass(frozen=True, slots=True)
class Skipped:
    """Message of the worker: ``ident`` was superseded, not run."""

    ident: int


type Message = Done | Failed | Skipped
type Spawn = Callable[[Callable[[], None]], None]


def start_thread(work: Callable[[], None]) -> None:
    """Run work on a new daemon thread.

    A daemon thread, so that closing the window never waits for a
    search that is still running.
    """
    threading.Thread(target=work, name="sift-search", daemon=True).start()


class Controller:
    """Connect a Backend to a View by a worker thread and a queue."""

    def __init__(
        self,
        backend: Backend,
        view: View,
        *,
        spawn: Spawn = start_thread,
    ) -> None:
        """Keep the backend and the view.

        spawn starts a function on another thread; a test passes a
        function that calls it at once, which makes the run
        deterministic.
        """
        self.backend = backend
        self.view = view
        self._spawn = spawn
        self._messages = queue.Queue[Message]()
        self._search_lock = threading.Lock()
        self._latest = 0  # only ever grows
        self._outcome: Outcome | None = None
        # what the preview shows: (outcome, row index), None if unknown
        self._shown: tuple[Outcome | None, int | None] | None = None
        self.pending = 0

    def submit(self, text: str) -> bool:
        """Start a search for text; return False if it is blank.

        Runs on the UI thread and returns before the search is done.
        ``pending`` counts the searches whose message has not been
        read by ``poll`` yet.
        """
        query = text.strip()
        if not query:
            self.view.show_status("请输入查询", error=False)
            return False
        self._latest += 1
        ident = self._latest
        self.pending += 1
        self.view.show_busy(True)
        self.view.show_status("搜索中…", error=False)
        self._spawn(lambda: self._work(ident, query))
        return True

    def _work(self, ident: int, query: str) -> None:
        """Search and queue the answer. Runs on the worker thread.

        One search runs at a time. A request that waited for the lock
        and is no longer the newest is skipped: its answer would be
        dropped anyway, and the newest must not wait behind it.
        """
        message: Message
        with self._search_lock:
            if ident != self._latest:
                message = Skipped(ident)
            else:
                try:
                    message = Done(ident, self.backend.search(query))
                except QuerySyntaxError as error:
                    message = Failed(ident, error.render())
                except SiftError as error:
                    message = Failed(ident, f"error: {error}")
                except Exception as error:
                    # a bug must reach the status line, not die here
                    log.exception("search failed")
                    message = Failed(
                        ident, f"error: {type(error).__name__}: {error}"
                    )
        self._messages.put(message)

    def poll(self) -> int:
        """Apply every message that has arrived; return how many.

        Runs on the UI thread, from ``root.after``. An answer for a
        query that is no longer the newest is read and dropped.
        """
        count = 0
        while True:
            try:
                message = self._messages.get_nowait()
            except queue.Empty:
                break
            count += 1
            self.pending -= 1
            if message.ident == self._latest:
                self._apply(message)
        if count and self.pending == 0:
            self.view.show_busy(False)
        return count

    def _apply(self, message: Message) -> None:
        """Show the answer of the newest query."""
        match message:
            case Done(_, outcome):
                self._outcome = outcome
                self._shown = None
                self.view.show_results(outcome.rows)
                self.view.show_status(outcome.status(), error=False)
                if outcome.rows:
                    self.select(0)
                    self.view.select_row(0)
                else:
                    self.view.show_preview(None)
            case Failed(_, text):
                self._outcome = None
                self._shown = None
                self.view.show_results([])
                self.view.show_preview(None)
                self.view.show_status(text, error=True)
            case Skipped():
                pass  # never the newest: poll does not get here

    def select(self, index: int | None) -> None:
        """Show the preview of row index, or none.

        Nothing is redrawn if the preview already shows that row of
        this outcome: the window reports a selection that the
        controller made itself.
        """
        outcome = self._outcome
        shown = self._shown
        if shown is not None and shown[0] is outcome and shown[1] == index:
            return
        if outcome is None or index is None:
            self._shown = (outcome, index)
            self.view.show_preview(None)
        elif 0 <= index < len(outcome.previews):
            self._shown = (outcome, index)
            self.view.show_preview(outcome.previews[index])

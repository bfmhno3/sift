"""The search on a thread of the global ``QThreadPool``.

``SearchWorker`` is a ``QRunnable``: ``pool.start(worker)`` queues
its ``run`` on a pooled thread, which a ``QThread`` would make you
create and tear down yourself. A ``QRunnable`` is not a ``QObject``
and has no signals, so the worker owns a small ``SearchSignals``
holder. Emitting a signal from the pool thread to a slot of an
object that lives in the UI thread is a queued connection: Qt puts
an event on the UI thread's loop and the slot runs there. The worker
never touches a widget.
"""

import logging
from typing import override

from PySide6.QtCore import QObject, QRunnable, Signal

from sift.errors import QuerySyntaxError, SiftError
from sift.gui.controller import Catalog
from sift.search import SearchResult

log = logging.getLogger(__name__)


class SearchSignals(QObject):
    """The signals of one search; the QRunnable cannot have its own.

    ``finished`` carries the SearchResult and the request id,
    ``failed`` the text to show and the request id.
    """

    finished = Signal(SearchResult, int)
    failed = Signal(str, int)


class SearchWorker(QRunnable):
    """Run one query and report it, tagged with its request id."""

    def __init__(self, catalog: Catalog, query: str, request_id: int) -> None:
        """Keep what ``run`` needs; the signals are connected later."""
        super().__init__()
        self.catalog = catalog
        self.query = query
        self.request_id = request_id
        self.signals = SearchSignals()

    @override
    def run(self) -> None:
        """Search on the pool thread and emit one of the signals."""
        try:
            result = self.catalog.find(self.query)
        except QuerySyntaxError as error:
            self.signals.failed.emit(error.render(), self.request_id)
        except SiftError as error:
            self.signals.failed.emit(f"error: {error}", self.request_id)
        except Exception as error:
            # a bug must reach the banner, not die on a pool thread
            log.exception("search failed")
            text = f"error: {type(error).__name__}: {error}"
            self.signals.failed.emit(text, self.request_id)
        else:
            self.signals.finished.emit(result, self.request_id)

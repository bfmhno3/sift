"""Start the Qt client: ``run`` is what ``sift gui`` calls."""

import os
import sys
from collections.abc import Sequence

from PySide6.QtCore import QElapsedTimer
from PySide6.QtWidgets import QApplication

from sift.errors import SiftError
from sift.gui.controller import Catalog
from sift.gui.qt.window import MainWindow


def has_display() -> bool:
    """Return False if Qt would abort for want of a display.

    On Linux Qt picks the xcb or wayland plugin and aborts the
    process, with no exception, if neither can connect. A set
    ``QT_QPA_PLATFORM`` (offscreen, say) is trusted.
    """
    if not sys.platform.startswith("linux"):
        return True
    return bool(
        os.environ.get("QT_QPA_PLATFORM")
        or os.environ.get("DISPLAY")
        or os.environ.get("WAYLAND_DISPLAY")
    )


def run(argv: Sequence[str], catalog: Catalog) -> int:
    """Open the window on catalog and run the event loop.

    Return the exit code of the loop. Raise SiftError if there is no
    display.
    """
    if not has_display():
        raise SiftError("cannot open a display: DISPLAY is not set")
    startup = QElapsedTimer()
    startup.start()
    app = QApplication(list(argv))
    app.setApplicationName("Sift")
    window = MainWindow(catalog, startup=startup)
    window.show()
    window.focus_search()
    return app.exec()

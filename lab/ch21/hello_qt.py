"""The smallest Qt program: an application, a widget, a layout.

Run it with ``QT_QPA_PLATFORM=offscreen`` and it draws into memory.
It also shows the two lives of a Qt object: the parent owns its
children (they die with it), and a Python name only keeps the wrapper.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def main() -> None:
    """Show a window for 100 ms, then quit the event loop."""
    app = QApplication(sys.argv)  # one per process, before any widget
    window = QWidget()
    window.setWindowTitle("hello")
    layout = QVBoxLayout(window)  # the layout takes `window` as owner
    layout.addWidget(QLabel("你好, Qt"))
    layout.addWidget(QPushButton("OK"))
    window.show()

    # ownership: the label is a child of the window, not of Python.
    # Dropping the Python name does not delete it.
    label = QLabel("kept alive by its parent", window)
    label.setObjectName("child")
    del label
    print(
        "children:",
        [c.objectName() or type(c).__name__ for c in window.children()],
    )
    print("found by name:", window.findChild(QLabel, "child") is not None)

    print("platform:", app.platformName())
    print("visible:", window.isVisible())
    print("size hint:", window.sizeHint().width() > 0)

    # the event loop runs until something calls quit; here a timer does
    QTimer.singleShot(100, app.quit)
    code = app.exec()
    print("exec returned", code)


if __name__ == "__main__":
    main()

"""Signals and slots: a custom Signal, connection types, a pitfall.

A signal is a list of callables kept by the sender. ``emit`` calls
them, in the order they were connected. Whether a slot runs at once
or later is the *connection type*: direct (a plain call), queued
(an event for the receiver's thread) or auto (decide at emit time).
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import (  # noqa: E402
    QCoreApplication,
    QObject,
    Qt,
    QTimer,
    Signal,
)


class Counter(QObject):
    """An object with one signal that carries an int."""

    changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.value = 0

    def bump(self) -> None:
        self.value += 1
        self.changed.emit(self.value)


def connection_types(app: QCoreApplication) -> None:
    """Direct runs inside emit, queued after the loop gets control."""
    counter = Counter()
    log: list[str] = []
    counter.changed.connect(
        lambda v: log.append(f"direct {v}"),
        Qt.ConnectionType.DirectConnection,
    )
    counter.changed.connect(
        lambda v: log.append(f"queued {v}"),
        Qt.ConnectionType.QueuedConnection,
    )
    counter.bump()
    log.append("bump returned")
    app.processEvents()  # the queued call is delivered here
    print("order:", log)


def lambda_pitfall() -> None:
    """A lambda closes over the variable, not over its value."""
    counter = Counter()
    seen: list[int] = []
    for i in range(3):
        # BAD: every lambda reads the same `i`, 2 after the loop
        counter.changed.connect(lambda _v: seen.append(i))  # noqa: B023
    counter.bump()
    print("late binding:", seen)

    counter2 = Counter()
    seen2: list[int] = []
    for i in range(3):
        # good: a default argument freezes the value of `i`
        counter2.changed.connect(lambda _v, i=i: seen2.append(i))
    counter2.bump()
    print("default arg:", seen2)


def disconnecting() -> None:
    """A connection can be removed; a dead receiver removes itself."""
    counter = Counter()
    hits: list[int] = []

    def slot(value: int) -> None:
        hits.append(value)

    counter.changed.connect(slot)
    counter.bump()
    counter.changed.disconnect(slot)
    counter.bump()
    print("after disconnect:", hits)


def main() -> None:
    app = QCoreApplication(sys.argv)
    connection_types(app)
    lambda_pitfall()
    disconnecting()
    QTimer.singleShot(0, app.quit)
    app.exec()


if __name__ == "__main__":
    main()

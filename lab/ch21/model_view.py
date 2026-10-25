"""A minimal model and a view: data in one object, pixels in another.

``QAbstractListModel`` needs two methods, ``rowCount`` and ``data``.
A *role* says which facet of an item the caller wants: display text,
a tooltip, or a custom value of your own.
"""

import os
import sys
from typing import override

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import (  # noqa: E402
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtWidgets import QApplication, QListView  # noqa: E402

ScoreRole = Qt.ItemDataRole.UserRole + 1


class Words(QAbstractListModel):
    """Words with a score; the view shows the word."""

    def __init__(self, items: list[tuple[str, float]]) -> None:
        super().__init__()
        self.items = items

    @override
    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),  # noqa: B008
    ) -> int:
        return 0 if parent.isValid() else len(self.items)

    @override
    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | float | None:
        if not index.isValid():
            return None
        word, score = self.items[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return word
        if role == ScoreRole:
            return score
        return None

    def set_score(self, row: int, score: float) -> None:
        """Change one score and tell the views which cell changed."""
        word, _ = self.items[row]
        self.items[row] = (word, score)
        index = self.index(row)
        self.dataChanged.emit(index, index, [ScoreRole])


def main() -> None:
    app = QApplication(sys.argv)
    model = Words([("rust", 2.5), ("kalman", 4.25), ("tea", 0.5)])
    view = QListView()
    view.setModel(model)
    view.resize(200, 120)
    view.show()

    print("rows:", model.rowCount())
    for row in range(model.rowCount()):
        index = model.index(row)
        print(
            row,
            model.data(index, Qt.ItemDataRole.DisplayRole),
            model.data(index, ScoreRole),
        )

    changes: list[tuple[int, list[int]]] = []
    model.dataChanged.connect(
        lambda top, _bottom, roles: changes.append((top.row(), list(roles)))
    )
    model.set_score(1, 9.0)
    print("dataChanged:", changes)

    model.beginResetModel()  # a bulk replace: views drop their state
    model.items = []
    model.endResetModel()
    print("rows after reset:", model.rowCount())
    app.processEvents()


if __name__ == "__main__":
    main()

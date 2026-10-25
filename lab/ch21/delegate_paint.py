"""A minimal delegate: paint a row yourself with a QPainter.

The view asks ``sizeHint`` for the size and calls ``paint`` with a
painter already clipped to the row. The script paints two colored
cards, grabs the view into an image and reads two pixels back.
"""

import os
import sys
from typing import override

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex, QRectF, QSize, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QPainter,
    QStandardItem,
    QStandardItemModel,  # noqa: E402
)
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QListView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

CARD = QColor("#4F46E5")
GAP = 8


class Cards(QStyledItemDelegate):
    """Draw each row as a rounded rectangle with its text."""

    @override
    def sizeHint(self, option: QStyleOptionViewItem, index: object) -> QSize:
        return QSize(option.rect.width(), 40 + GAP)

    @override
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(0, 0, 0, -GAP)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(CARD)
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(
            rect.adjusted(12, 0, 0, 0),
            int(Qt.AlignmentFlag.AlignVCenter),
            str(index.data(Qt.ItemDataRole.DisplayRole)),
        )
        painter.restore()


def main() -> None:
    app = QApplication(sys.argv)
    model = QStandardItemModel()
    for word in ("first", "second"):
        model.appendRow(QStandardItem(word))
    view = QListView()
    view.setModel(model)
    view.setItemDelegate(Cards(view))
    view.setFrameShape(QListView.Shape.NoFrame)
    view.resize(240, 140)
    view.show()
    app.processEvents()

    image = view.grab().toImage()
    inside = image.pixelColor(120, 20)  # in the first card
    gap = image.pixelColor(120, 44)  # between the cards
    print("size:", image.width(), "x", image.height())
    print("inside card:", inside.name())
    print("in the gap :", gap.name())
    print("card color painted:", inside.name() == CARD.name())


if __name__ == "__main__":
    main()

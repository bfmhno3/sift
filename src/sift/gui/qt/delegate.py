"""The delegate that paints a result as a card.

A view asks its delegate two questions: ``sizeHint`` (how tall is
this row?) and ``paint`` (draw it into this rectangle). Here both
answers come from the same arithmetic on ``QFontMetrics`` and
``QTextLayout``, so a card is always exactly as tall as what is
drawn in it and nothing is clipped::

    +--------------------------------------------+  12 px padding
    | Title, 15 px semibold, elided         [2.41]|  pill on the right
    | 2026-03-02  Tutorial  [rust] [lifetime]     |  meta, 12 px
    | ... a snippet of at most two lines with the |
    | hits on a ``mark_bg`` ground, radius 3 ...  |
    +--------------------------------------------+  12 px padding
                                                     8 px between cards
"""

from dataclasses import dataclass
from typing import cast, override

from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QPointF,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
    QTextLayout,
    QTextLine,
    QTextOption,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from sift.gui.qt.model import Card, CardRole
from sift.gui.qt.theme import (
    RADIUS_CARD,
    SIZE_BODY,
    SIZE_META,
    SIZE_TITLE,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    Tokens,
    make_font,
)

type Index = QModelIndex | QPersistentModelIndex

GAP = SPACE_2  # between cards
PAD_X = SPACE_4
PAD_Y = SPACE_3
PILL_H = 22
CHIP_H = 20
SNIPPET_LINES = 2
MARK_RADIUS = 3
DEFAULT_WIDTH = 400


@dataclass(frozen=True, slots=True)
class Snippet:
    """A snippet laid out in a width: the layout and the hit spans."""

    layout: QTextLayout
    spans: list[tuple[int, int]]
    height: float


def lay_out(text: str, font: QFont, width: float) -> QTextLayout:
    """Break text into lines of at most width pixels.

    Lines may break between any two CJK characters and at spaces in
    Latin text; a word longer than a line is cut.
    """
    layout = QTextLayout(text, font)
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    layout.setTextOption(option)
    layout.setCacheEnabled(True)
    layout.beginLayout()
    y = 0.0
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(width)
        line.setPosition(QPointF(0.0, y))
        y += line.height()
    layout.endLayout()
    return layout


def x_of(line: QTextLine, position: int) -> float:
    """Return the x of the text position in line.

    PySide6 declares ``cursorToX`` as returning ``object``; it
    returns the pair (x, cursor position).
    """
    x, _ = cast(tuple[float, int], line.cursorToX(position))
    return x


def fit_snippet(
    parts: list[tuple[str, bool]],
    font: QFont,
    width: float,
    max_lines: int = SNIPPET_LINES,
) -> Snippet:
    """Lay out the snippet parts in at most max_lines lines.

    If the text is longer, it is cut at the end of the last line and
    ends with an ellipsis; the cut is made on the text, and the hit
    spans are clipped to it, so the painted text is the laid out
    text.
    """
    text = "".join(piece for piece, _ in parts).replace("\n", " ")
    spans: list[tuple[int, int]] = []
    cursor = 0
    for piece, is_hit in parts:
        if is_hit:
            spans.append((cursor, cursor + len(piece)))
        cursor += len(piece)
    layout = lay_out(text, font, width)
    if layout.lineCount() > max_lines:
        last = layout.lineAt(max_lines - 1)
        end = last.textStart() + last.textLength()
        while True:
            text = text[:end].rstrip() + "…"
            layout = lay_out(text, font, width)
            if layout.lineCount() <= max_lines or end <= 1:
                break
            end -= 1
        limit = len(text) - 1
        spans = [(a, min(b, limit)) for a, b in spans if a < limit]
    height = sum(layout.lineAt(i).height() for i in range(layout.lineCount()))
    return Snippet(layout, spans, height)


class ResultDelegate(QStyledItemDelegate):
    """Paint every row of the results list as a card."""

    def __init__(self, tokens: Tokens, parent: QAbstractItemView) -> None:
        """Make the fonts once; ``set_tokens`` swaps the colors."""
        super().__init__(parent)
        self.tokens = tokens
        self.title_font = make_font(SIZE_TITLE, semibold=True)
        self.meta_font = make_font(SIZE_META)
        self.chip_font = make_font(SIZE_META - 1)
        self.pill_font = make_font(SIZE_META, semibold=True)
        self.snippet_font = make_font(SIZE_BODY)

    def set_tokens(self, tokens: Tokens) -> None:
        """Use the colors of tokens from the next paint on."""
        self.tokens = tokens

    def row_width(self, option: QStyleOptionViewItem) -> int:
        """Return the width a card has: the viewport of the view."""
        view = option.widget
        if isinstance(view, QAbstractItemView):
            return max(view.viewport().width(), 1)
        return option.rect.width() or DEFAULT_WIDTH

    def snippet_for(self, card: Card, card_width: float) -> Snippet:
        """Lay out the snippet of card inside a card of card_width."""
        return fit_snippet(
            card.snippet, self.snippet_font, card_width - 2 * PAD_X
        )

    def top_height(self) -> float:
        """Return the height of the title row."""
        title = QFontMetrics(self.title_font).height()
        return float(max(title, PILL_H))

    @override
    def sizeHint(self, option: QStyleOptionViewItem, index: Index) -> QSize:
        """Return the size of the card of index, gap included."""
        card = index.data(CardRole)
        width = self.row_width(option)
        if not isinstance(card, Card):
            return QSize(width, 0)
        snippet = self.snippet_for(card, width)
        height = 2 * PAD_Y + self.top_height() + SPACE_1 + CHIP_H
        if snippet.spans or snippet.layout.text():
            height += SPACE_2 + snippet.height
        return QSize(width, int(height + 0.999) + GAP)

    @override
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: Index,
    ) -> None:
        """Paint the card of index into option.rect."""
        card = index.data(CardRole)
        if not isinstance(card, Card):
            return
        state = option.state
        selected = bool(state & QStyle.StateFlag.State_Selected)
        hover = bool(state & QStyle.StateFlag.State_MouseOver)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(option.rect).adjusted(0, 0, 0, -GAP)
        self.paint_card_box(painter, rect, selected, hover)
        inner = rect.adjusted(PAD_X, PAD_Y, -PAD_X, -PAD_Y)
        top = self.paint_title_row(painter, card, inner, selected)
        meta_y = inner.top() + top + SPACE_1
        self.paint_meta_row(painter, card, inner, meta_y, selected)
        snippet = self.snippet_for(card, rect.width())
        text_y = meta_y + CHIP_H + SPACE_2
        self.paint_snippet(painter, snippet, inner.left(), text_y)
        painter.restore()

    def paint_card_box(
        self,
        painter: QPainter,
        rect: QRectF,
        selected: bool,
        hover: bool,
    ) -> None:
        """Fill the card and draw its border.

        Selected: 2 px accent border on ``accent_soft``. Hover: the
        accent at 40% alpha. Otherwise 1 px ``border`` on ``surface``.
        """
        t = self.tokens
        if selected:
            fill, pen, half = (
                QColor(t.accent_soft),
                QPen(QColor(t.accent), 2),
                1.0,
            )
        elif hover:
            edge = QColor(t.accent)
            edge.setAlphaF(0.4)
            fill, pen, half = QColor(t.surface), QPen(edge, 1), 0.5
        else:
            fill, pen, half = QColor(t.surface), QPen(QColor(t.border), 1), 0.5
        painter.setPen(pen)
        painter.setBrush(fill)
        painter.drawRoundedRect(
            rect.adjusted(half, half, -half, -half), RADIUS_CARD, RADIUS_CARD
        )

    def paint_title_row(
        self,
        painter: QPainter,
        card: Card,
        inner: QRectF,
        selected: bool,
    ) -> float:
        """Draw the title and the score pill; return the row height."""
        t = self.tokens
        height = self.top_height()
        pill_metrics = QFontMetrics(self.pill_font)
        pill_w = pill_metrics.horizontalAdvance(card.score_text) + 2 * SPACE_3
        pill = QRectF(
            inner.right() - pill_w,
            inner.top() + (height - PILL_H) / 2,
            pill_w,
            PILL_H,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(t.surface if selected else t.accent_soft))
        painter.drawRoundedRect(pill, PILL_H / 2, PILL_H / 2)
        painter.setFont(self.pill_font)
        painter.setPen(QColor(t.accent))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, card.score_text)

        title_w = int(inner.width() - pill_w - SPACE_2)
        title = QFontMetrics(self.title_font).elidedText(
            card.title, Qt.TextElideMode.ElideRight, title_w
        )
        painter.setFont(self.title_font)
        painter.setPen(QColor(t.text))
        painter.drawText(
            QRectF(inner.left(), inner.top(), title_w, height),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            title,
        )
        return height

    def paint_meta_row(
        self,
        painter: QPainter,
        card: Card,
        inner: QRectF,
        y: float,
        selected: bool,
    ) -> None:
        """Draw the date, the category and up to three tag chips."""
        t = self.tokens
        meta = QFontMetrics(self.meta_font)
        chip_metrics = QFontMetrics(self.chip_font)
        x = inner.left()
        painter.setFont(self.meta_font)
        painter.setPen(QColor(t.muted))
        for text in (card.date, card.category):
            if not text:
                continue
            width = meta.horizontalAdvance(text)
            painter.drawText(
                QRectF(x, y, width + 1, CHIP_H),
                int(Qt.AlignmentFlag.AlignVCenter),
                text,
            )
            x += width + SPACE_3
        painter.setFont(self.chip_font)
        for tag in card.tags:
            width = chip_metrics.horizontalAdvance(tag) + 2 * SPACE_2
            if x + width > inner.right():
                break
            chip = QRectF(x, y, width, CHIP_H)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(t.surface if selected else t.surface_alt))
            painter.drawRoundedRect(chip, CHIP_H / 2, CHIP_H / 2)
            painter.setPen(QColor(t.muted))
            painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, tag)
            x += width + SPACE_1

    def paint_snippet(
        self, painter: QPainter, snippet: Snippet, x: float, y: float
    ) -> None:
        """Draw the snippet lines; hits sit on a rounded mark_bg box.

        The boxes go first, the text over them in ``mark_text``:
        a ``QTextLayout`` draws text with the colors of its format
        ranges, and has no notion of a rounded background.
        """
        t = self.tokens
        layout = snippet.layout
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(t.mark_bg))
        for i in range(layout.lineCount()):
            line = layout.lineAt(i)
            first = line.textStart()
            last = first + line.textLength()
            for start, end in snippet.spans:
                a, b = max(start, first), min(end, last)
                if a >= b:
                    continue
                left = x_of(line, a)
                right = x_of(line, b)
                box = QRectF(
                    x + left - 1,
                    y + line.y() + 1,
                    right - left + 2,
                    line.height() - 2,
                )
                painter.drawRoundedRect(box, MARK_RADIUS, MARK_RADIUS)
        formats: list[QTextLayout.FormatRange] = []
        for start, end in snippet.spans:
            fmt_range = QTextLayout.FormatRange()
            fmt_range.start = start
            fmt_range.length = end - start
            fmt_range.format.setForeground(QColor(t.mark_text))
            formats.append(fmt_range)
        painter.setPen(QColor(t.text))
        snippet.layout.draw(painter, QPointF(x, y), formats)

"""The preview pane: a ``QTextBrowser`` that shows one post.

The text is the original Markdown of the post, rendered by
``QTextDocument.setMarkdown``. The title and the meta line are
blocks put in front of it, the hits are found with
``QTextDocument.find`` and marked with a merged ``QTextCharFormat``:
the document keeps its own formatting (headings, code, lists) and
the highlight is one more property on top of it.
"""

from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QResizeEvent,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import QTextBrowser, QWidget

from sift.gui.qt.theme import (
    MONO_FAMILIES,
    SIZE_HEADER,
    SIZE_META,
    SPACE_2,
    SPACE_4,
    SPACE_5,
    Tokens,
)

MAX_TEXT_WIDTH = 720
MAX_MARKS = 2000
LINE_HEIGHT_PERCENT = 150


class PreviewBrowser(QTextBrowser):
    """Show a post with its hits, in a column of at most 720 px."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Make the browser read-only, with links opened outside."""
        super().__init__(parent)
        self.setOpenExternalLinks(True)
        self.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.document().setDocumentMargin(0)
        self.marks = 0
        self._apply_margins()

    def _apply_margins(self) -> None:
        """Center the text column: 24 px, or more in a wide pane."""
        side = max(SPACE_5, (self.width() - MAX_TEXT_WIDTH) // 2)
        self.setViewportMargins(side, SPACE_5, side, SPACE_5)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the column centered when the pane changes size."""
        super().resizeEvent(event)
        self._apply_margins()

    def show_post(
        self,
        title: str,
        meta: str,
        markdown: str,
        terms: set[str],
        tokens: Tokens,
    ) -> None:
        """Replace the document by one post and mark the terms."""
        doc = self.document()
        doc.setMarkdown(markdown)
        # One edit block for every format change below: each change
        # inside it would otherwise lay the whole post out again, a
        # second of work on the UI thread for a long post.
        edit = QTextCursor(doc)
        edit.beginEditBlock()
        self._put_header(doc, title, meta, tokens)
        self._set_line_height(doc)
        self._use_mono_for_code(doc)
        self.marks = mark_terms(doc, terms, tokens)
        edit.endEditBlock()
        self.moveCursor(QTextCursor.MoveOperation.Start)
        self.verticalScrollBar().setValue(0)

    def clear_post(self) -> None:
        """Empty the preview."""
        self.document().clear()
        self.marks = 0

    def _put_header(
        self, doc: QTextDocument, title: str, meta: str, tokens: Tokens
    ) -> None:
        """Insert the title and the meta line before the first block.

        ``insertBlock`` with the formats of the old first block keeps
        that block as it was (a heading stays a heading); the two
        empty blocks in front of it get the title and the meta.
        """
        cursor = QTextCursor(doc)
        block_format = cursor.blockFormat()
        char_format = cursor.charFormat()
        cursor.insertBlock(block_format, char_format)
        cursor.insertBlock(block_format, char_format)

        title_font = QFont(self.font())
        title_font.setPixelSize(SIZE_HEADER)
        title_font.setWeight(QFont.Weight.DemiBold)
        title_format = QTextCharFormat()
        title_format.setFont(title_font)
        title_format.setForeground(QColor(tokens.text))
        meta_font = QFont(self.font())
        meta_font.setPixelSize(SIZE_META)
        meta_format = QTextCharFormat()
        meta_format.setFont(meta_font)
        meta_format.setForeground(QColor(tokens.muted))

        for number, text, fmt, after in (
            (0, title, title_format, SPACE_2),
            (1, meta, meta_format, SPACE_4),
        ):
            block = QTextCursor(doc.findBlockByNumber(number))
            plain = QTextBlockFormat()
            plain.setBottomMargin(after)
            block.setBlockFormat(plain)
            block.insertText(text, fmt)

    def _set_line_height(self, doc: QTextDocument) -> None:
        """Give every block a line height of 150%."""
        fmt = QTextBlockFormat()
        fmt.setLineHeight(
            LINE_HEIGHT_PERCENT,
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.mergeBlockFormat(fmt)

    def _use_mono_for_code(self, doc: QTextDocument) -> None:
        """Set the monospace families on every fixed-pitch fragment."""
        spans: list[tuple[int, int]] = []
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.charFormat().fontFixedPitch():
                    start = fragment.position()
                    spans.append((start, start + fragment.length()))
                it += 1
            block = block.next()
        code = QTextCharFormat()
        code.setFontFamilies(MONO_FAMILIES)
        for start, end in spans:
            cursor = QTextCursor(doc)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(code)


def mark_terms(doc: QTextDocument, terms: set[str], tokens: Tokens) -> int:
    """Mark every occurrence of every term in doc; return how many.

    ``find`` is case-insensitive by default and moves a cursor to the
    match; ``mergeCharFormat`` on that cursor adds the background and
    the text color to what the fragment already has. At most
    ``MAX_MARKS`` matches are marked: a one-character CJK term in a
    long post would otherwise make the selection slow.
    """
    mark = QTextCharFormat()
    mark.setBackground(QColor(tokens.mark_bg))
    mark.setForeground(QColor(tokens.mark_text))
    count = 0
    for term in sorted(terms):
        cursor = doc.find(term)
        while not cursor.isNull() and count < MAX_MARKS:
            cursor.mergeCharFormat(mark)
            count += 1
            cursor = doc.find(term, cursor)
    return count

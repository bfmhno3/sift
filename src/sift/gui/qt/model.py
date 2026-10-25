"""The list model of the results: one ``Card`` per hit.

``ResultsModel`` is a ``QAbstractListModel``. A model owns data and
tells views when it changes; it draws nothing. The delegate asks for
``CardRole`` and paints the whole card from it, ``Qt.DisplayRole``
(the title) and ``Qt.ToolTipRole`` (the path) exist for the parts of
Qt that do not know the card: the accessibility bridge and tooltips.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import override

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)

from sift.document import Document
from sift.search import SearchResult

CardRole = Qt.ItemDataRole.UserRole + 1
MAX_TAGS = 3

type Index = QModelIndex | QPersistentModelIndex


@dataclass(frozen=True, slots=True)
class Card:
    """Everything one result card shows."""

    doc_id: int
    title: str
    score: float
    date: str
    category: str
    tags: tuple[str, ...]
    snippet: list[tuple[str, bool]]
    path: Path

    @property
    def score_text(self) -> str:
        """Return the score as the pill shows it.

        >>> Card(1, "t", 2.345, "", "", (), [], Path("a.md")).score_text
        '2.35'
        """
        return f"{self.score:.2f}"


def make_cards(
    result: SearchResult, document: Callable[[int], Document]
) -> list[Card]:
    """Return a Card for every hit of result.

    document fetches the Document of a doc id: the hit has the title,
    the score and the snippet, the document the date, the category
    and the tags.
    """
    cards: list[Card] = []
    for hit in result.hits:
        doc = document(hit.doc_id)
        cards.append(
            Card(
                doc_id=hit.doc_id,
                title=hit.title,
                score=hit.score,
                date=f"{doc.published:%Y-%m-%d}",
                category=doc.category or "",
                tags=doc.tags[:MAX_TAGS],
                snippet=hit.snippet,
                path=hit.path,
            )
        )
    return cards


class ResultsModel(QAbstractListModel):
    """A flat list of cards; the rows are replaced as a whole."""

    def __init__(self) -> None:
        """Start with no rows."""
        super().__init__()
        self._cards: list[Card] = []

    @override
    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        """Return the number of cards; a flat list has no children."""
        return 0 if parent.isValid() else len(self._cards)

    @override
    def data(
        self,
        index: Index,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Card | str | None:
        """Return the card, the title or the path for role."""
        if not index.isValid() or not 0 <= index.row() < len(self._cards):
            return None
        card = self._cards[index.row()]
        if role == CardRole:
            return card
        if role == Qt.ItemDataRole.DisplayRole:
            return card.title
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(card.path)
        return None

    def card(self, row: int) -> Card | None:
        """Return the card of row, or None if there is no such row."""
        if 0 <= row < len(self._cards):
            return self._cards[row]
        return None

    def set_cards(self, cards: list[Card]) -> None:
        """Replace every row; views reset and drop their selection."""
        self.beginResetModel()
        self._cards = cards
        self.endResetModel()

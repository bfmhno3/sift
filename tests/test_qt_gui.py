"""Tests of the Qt window, on the offscreen platform.

``tests/conftest.py`` sets ``QT_QPA_PLATFORM=offscreen`` before Qt is
imported, so the windows are real widgets that draw into memory and
nothing appears on a screen. pytest-qt supplies ``qtbot``: it makes
the QApplication, sends key events, and runs the event loop while it
waits for a condition.
"""

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QPoint, QSize, Qt  # noqa: E402
from PySide6.QtGui import QColor, QPalette, QTextDocument  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QListView,
    QStyleOptionViewItem,
)
from pytestqt.qtbot import QtBot  # noqa: E402

from sift.corpus import iter_documents  # noqa: E402
from sift.document import Document  # noqa: E402
from sift.gui.controller import IndexBackend  # noqa: E402
from sift.gui.qt.delegate import ResultDelegate, fit_snippet  # noqa: E402
from sift.gui.qt.model import Card, ResultsModel  # noqa: E402
from sift.gui.qt.preview import mark_terms  # noqa: E402
from sift.gui.qt.theme import (  # noqa: E402
    DARK,
    LIGHT,
    generate_qss,
    make_font,
)
from sift.gui.qt.window import MainWindow  # noqa: E402
from sift.index import IndexWriter, InvertedIndex  # noqa: E402
from sift.search import Searcher, SearchResult  # noqa: E402

POSTS = {
    "kalman.md": """---
title: Kalman filter in one dimension
published: "2026-02-03 08:00:00 +08:00"
tags:
  - Math
  - Control
category: Tutorial
---

# Kalman filter

A Kalman filter predicts the state, then corrects it with a
measurement. The gain says how much to trust the measurement.
""",
    "rust.md": """---
title: Rust 所有权入门
published: "2026-03-02 08:00:00 +08:00"
tags:
  - Rust
category: Tutorial
---

# 所有权

Rust 用所有权规则管理内存，每个值只有一个所有者。
""",
    "tea.md": """---
title: Tea
published: "2026-01-01 08:00:00 +08:00"
tags: []
category: Notes
---

Water at eighty degrees.
""",
}


@pytest.fixture
def backend(tmp_path: Path) -> IndexBackend:
    """Return a backend over a three-post corpus with a Kalman post."""
    root = tmp_path / "posts"
    root.mkdir()
    for name, text in POSTS.items():
        (root / name).write_text(text, encoding="utf-8")
    index = InvertedIndex()
    with IndexWriter(index) as writer:
        for doc in iter_documents(root):
            writer.add(doc)
    return IndexBackend(Searcher(index), 10)


@pytest.fixture
def opened() -> list[Path]:
    """Collect the paths that Ctrl+O asks the desktop to open."""
    return []


@pytest.fixture
def window(
    qtbot: QtBot, backend: IndexBackend, opened: list[Path]
) -> Iterator[MainWindow]:
    """Return a shown, light window on the three posts."""
    win = MainWindow(backend, scheme="light", opener=opened.append)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    win.activateWindow()
    qtbot.waitActive(win)
    yield win
    win.close()


def type_query(qtbot: QtBot, win: MainWindow, text: str) -> None:
    """Type text into the search box, key by key."""
    qtbot.keyClicks(win.search_edit, text)


def wait_for_rows(qtbot: QtBot, win: MainWindow, count: int = 1) -> None:
    """Wait until the model holds at least count rows."""
    qtbot.waitUntil(lambda: win.model.rowCount() >= count, timeout=5000)


def test_typing_then_the_debounce_shows_rows(
    qtbot: QtBot, window: MainWindow
) -> None:
    type_query(qtbot, window, "kalman")
    assert window.model.rowCount() == 0  # the timer has not fired yet
    assert window.debounce.isActive()
    wait_for_rows(qtbot, window)
    card = window.model.card(0)
    assert card is not None and "Kalman" in card.title
    assert window.current_row() == 0
    assert "1 条结果" in window.status_label.text()


def test_every_key_restarts_the_timer(
    qtbot: QtBot, window: MainWindow
) -> None:
    searched: list[str] = []
    original = window.search_now

    def spy() -> None:
        searched.append(window.search_edit.text())
        original()

    window.debounce.timeout.disconnect()
    window.debounce.timeout.connect(spy)
    for letter in "kalman":
        qtbot.keyClick(window.search_edit, letter)
        qtbot.wait(50)  # less than the 200 ms of the timer
    qtbot.waitUntil(lambda: bool(searched), timeout=2000)
    assert searched == ["kalman"]


def test_a_syntax_error_shows_the_banner_with_a_caret(
    qtbot: QtBot, window: MainWindow
) -> None:
    type_query(qtbot, window, "(rust")
    qtbot.waitUntil(lambda: not window.banner.isHidden(), timeout=5000)
    assert "^" in window.banner.text()
    assert "(rust" in window.banner.text()
    assert window.model.rowCount() == 0
    type_query(qtbot, window, ")")
    qtbot.waitUntil(lambda: window.banner.isHidden(), timeout=5000)
    assert window.model.rowCount() >= 1


def test_no_match_shows_the_empty_page(
    qtbot: QtBot, window: MainWindow
) -> None:
    type_query(qtbot, window, "zzzzqqqq")
    qtbot.waitUntil(
        lambda: window.body.currentWidget() is window.empty_page,
        timeout=5000,
    )
    assert window.status_label.text().startswith("0 条结果")


def test_ctrl_k_focuses_the_search_box(
    qtbot: QtBot, window: MainWindow
) -> None:
    window.list_view.setFocus()
    assert not window.search_edit.hasFocus()
    qtbot.keyClick(window, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    assert window.search_edit.hasFocus()


def test_escape_clears_the_box_and_the_rows(
    qtbot: QtBot, window: MainWindow
) -> None:
    type_query(qtbot, window, "kalman")
    wait_for_rows(qtbot, window)
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    assert window.search_edit.text() == ""
    assert window.model.rowCount() == 0
    assert window.body.currentWidget() is window.start_page


def test_up_and_down_move_the_selection(
    qtbot: QtBot, window: MainWindow
) -> None:
    type_query(qtbot, window, "kalman OR rust OR water")
    wait_for_rows(qtbot, window, 3)
    assert window.current_row() == 0
    qtbot.keyClick(window.search_edit, Qt.Key.Key_Down)
    assert window.current_row() == 1
    qtbot.keyClick(window.search_edit, Qt.Key.Key_Up)
    qtbot.keyClick(window.search_edit, Qt.Key.Key_Up)
    assert window.current_row() == 0


def test_enter_searches_at_once(qtbot: QtBot, window: MainWindow) -> None:
    window.search_edit.setText("kalman")
    qtbot.keyClick(window.search_edit, Qt.Key.Key_Return)
    assert not window.debounce.isActive()
    wait_for_rows(qtbot, window)


def test_ctrl_o_opens_the_selected_file(
    qtbot: QtBot, window: MainWindow, opened: list[Path]
) -> None:
    qtbot.keyClick(window, Qt.Key.Key_O, Qt.KeyboardModifier.ControlModifier)
    assert opened == []  # nothing selected yet
    type_query(qtbot, window, "kalman")
    wait_for_rows(qtbot, window)
    qtbot.keyClick(window, Qt.Key.Key_O, Qt.KeyboardModifier.ControlModifier)
    assert [path.name for path in opened] == ["kalman.md"]


def test_an_example_chip_searches_it(qtbot: QtBot, window: MainWindow) -> None:
    chip = window.start_page.chips[0]
    assert chip.text() == "rust 所有权"
    qtbot.mouseClick(chip, Qt.MouseButton.LeftButton)
    assert window.search_edit.text() == "rust 所有权"
    wait_for_rows(qtbot, window)


def test_theme_toggle_switches_the_style_sheet_and_palette(
    qtbot: QtBot, window: MainWindow
) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    assert app.styleSheet() == generate_qss(LIGHT)
    assert window.palette().color(QPalette.ColorRole.Window) == QColor(
        LIGHT.bg
    )
    qtbot.mouseClick(window.theme_button, Qt.MouseButton.LeftButton)
    assert window.scheme == "dark"
    assert app.styleSheet() == generate_qss(DARK)
    assert window.palette().color(QPalette.ColorRole.Window) == QColor(DARK.bg)
    assert window.delegate.tokens is DARK
    qtbot.mouseClick(window.theme_button, Qt.MouseButton.LeftButton)
    assert app.styleSheet() == generate_qss(LIGHT)


def test_a_manual_theme_ignores_the_system(
    qtbot: QtBot, window: MainWindow
) -> None:
    window.toggle_theme()
    window._on_system_scheme(Qt.ColorScheme.Light)
    assert window.scheme == "dark"


def test_the_system_scheme_is_followed_until_the_user_chooses(
    qtbot: QtBot, window: MainWindow
) -> None:
    window._on_system_scheme(Qt.ColorScheme.Dark)
    assert window.scheme == window.system_scheme()


class GatedCatalog:
    """A catalog whose search for one query waits for a gate."""

    def __init__(self, inner: IndexBackend, slow: str) -> None:
        self.inner = inner
        self.slow = slow
        self.gate = threading.Event()

    @property
    def n_docs(self) -> int:
        return self.inner.n_docs

    @property
    def logs_queries(self) -> bool:
        return False

    def find(self, query: str) -> SearchResult:
        if query == self.slow:
            self.gate.wait(5)
        return self.inner.find(query)

    def terms(self, query: str) -> set[str]:
        return self.inner.terms(query)

    def document(self, doc_id: int) -> Document:
        return self.inner.document(doc_id)


def test_a_stale_answer_is_dropped(
    qtbot: QtBot, backend: IndexBackend
) -> None:
    catalog = GatedCatalog(backend, slow="kalman")
    win = MainWindow(catalog, scheme="light")
    qtbot.addWidget(win)
    win.search_edit.setText("kalman")
    win.search_now()  # request 1 waits at the gate
    win.search_edit.setText("water")
    win.search_now()  # request 2 is newer and answers first
    wait_for_rows(qtbot, win)
    catalog.gate.set()  # request 1 answers now, and must be ignored
    qtbot.wait(300)
    card = win.model.card(0)
    assert card is not None and card.title == "Tea"
    assert win.model.rowCount() == 1
    win.close()


def test_the_preview_marks_the_hits(qtbot: QtBot, window: MainWindow) -> None:
    type_query(qtbot, window, "kalman")
    wait_for_rows(qtbot, window)
    assert window.preview.marks >= 2
    assert "Kalman filter in one dimension" in window.preview.toPlainText()
    cursor = window.preview.document().find("Kalman")
    assert cursor.charFormat().background().color() == QColor(LIGHT.mark_bg)


def test_mark_terms_is_case_insensitive_and_counts() -> None:
    doc = QTextDocument()
    doc.setPlainText("Fox fox FOX dog")
    assert mark_terms(doc, {"fox"}, LIGHT) == 3


def test_the_preview_column_is_at_most_720_px(
    qtbot: QtBot, window: MainWindow
) -> None:
    window.resize(2000, 900)
    qtbot.wait(50)
    assert window.preview.viewport().width() <= 720


def test_cjk_query_marks_the_preview(qtbot: QtBot, window: MainWindow) -> None:
    # QTest cannot type CJK key by key: set the text, as an IME would
    window.search_edit.setText("所有权")
    wait_for_rows(qtbot, window)
    assert window.preview.marks >= 1


def test_the_status_says_the_log_is_written_when_it_is(
    qtbot: QtBot, backend: IndexBackend, tmp_path: Path
) -> None:
    backend.log_path = tmp_path / "log.db"
    assert backend.logs_queries
    win = MainWindow(backend, scheme="light")
    qtbot.addWidget(win)
    win.search_edit.setText("kalman")
    win.search_now()
    wait_for_rows(qtbot, win)
    assert win.status_label.text().endswith("查询日志已记录")


def card(snippet: list[tuple[str, bool]], title: str = "T") -> Card:
    return Card(
        1, title, 1.5, "2026-01-01", "Notes", ("a", "b"), snippet, Path("x.md")
    )


def test_cards_are_as_tall_as_their_content(qtbot: QtBot) -> None:
    view = QListView()
    qtbot.addWidget(view)
    view.resize(520, 600)
    model = ResultsModel()
    view.setModel(model)
    delegate = ResultDelegate(LIGHT, view)
    view.setItemDelegate(delegate)
    view.show()
    qtbot.waitExposed(view)
    long_text = "测试 " * 80
    short = card([("short", True)])
    long = card([(long_text, False)], "A very long title " * 10)
    model.set_cards([short, long])
    option = QStyleOptionViewItem()
    option.initFrom(view)
    option.widget = view
    heights = [
        delegate.sizeHint(option, model.index(row)).height()
        for row in range(2)
    ]
    one_line = fit_snippet(short.snippet, delegate.snippet_font, 488)
    two_lines = fit_snippet(long.snippet, delegate.snippet_font, 488)
    assert one_line.layout.lineCount() == 1
    assert two_lines.layout.lineCount() == 2
    assert two_lines.layout.text().endswith("…")
    assert heights[1] - heights[0] == pytest.approx(
        two_lines.height - one_line.height, abs=1
    )
    assert delegate.sizeHint(option, model.index(5)) == QSize(
        view.viewport().width(), 0
    )
    pos = view.visualRect(model.index(0)).center()
    assert view.indexAt(QPoint(pos.x(), pos.y())).row() == 0


def test_the_ellipsis_clips_the_hit_spans() -> None:
    parts = [("x" * 400, False), ("hit", True)]
    snippet = fit_snippet(parts, make_font(13), 200)
    assert snippet.layout.lineCount() == 2
    assert snippet.spans == []  # the hit was cut away with the tail


def test_tokens_cover_the_brief() -> None:
    assert (LIGHT.bg, LIGHT.accent, LIGHT.mark_bg) == (
        "#F7F8FA",
        "#4F46E5",
        "#FDE68A",
    )
    assert (DARK.bg, DARK.accent, DARK.error_soft) == (
        "#0F1117",
        "#818CF8",
        "#3B1212",
    )
    for tokens in (LIGHT, DARK):
        qss = generate_qss(tokens)
        for widget in (
            "QWidget",
            "QLineEdit",
            "QPushButton",
            "QListView",
            "QTextBrowser",
            "QScrollBar",
            "QSplitter::handle",
            "QStatusBar",
            "QToolTip",
            "QMenu",
        ):
            assert widget in qss
        assert tokens.surface in qss and tokens.error_soft in qss

"""The main window of the Qt client.

::

    +--------------------------------------------------------+
    | Sift [123 篇]  ( [search field, 44 px]        ) [moon] |  header
    | banner: syntax error with the caret line               |
    |========================================================|  2 px busy line
    |  +--------------+  +-------------------------------+   |
    |  | card         |  | title, meta                   |   |
    |  | card         |  | body, hits marked             |   |  44% / 56%
    |  +--------------+  +-------------------------------+   |
    | N 条结果 · X ms · 查询日志已记录                         |  status bar
    +--------------------------------------------------------+

The window owns no search logic. Typing restarts a 200 ms timer; when
it fires, a ``SearchWorker`` goes to the thread pool with a new
request id, and the window applies the answer whose id is still the
newest. Everything here runs on the UI thread except the worker.
"""

import time
from collections.abc import Callable
from pathlib import Path
from typing import override

from PySide6.QtCore import (
    QElapsedTimer,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QGuiApplication,
    QKeyEvent,
    QKeySequence,
    QPaintEvent,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sift.document import Document
from sift.gui.controller import Catalog
from sift.gui.qt.delegate import ResultDelegate
from sift.gui.qt.model import ResultsModel, make_cards
from sift.gui.qt.preview import PreviewBrowser
from sift.gui.qt.theme import (
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    TOKENS,
    Scheme,
    Tokens,
    apply_theme,
    icon,
)
from sift.gui.qt.worker import SearchWorker
from sift.markdown import split_front_matter
from sift.search import SearchResult

WIDTH = 1200
HEIGHT = 760
MIN_WIDTH = 900
MIN_HEIGHT = 600
FIELD_HEIGHT = 44
FIELD_MAX_WIDTH = 760
DEBOUNCE_MS = 200
RESULTS_SHARE = 44  # percent of the body; the preview gets the rest
EXAMPLES = (
    "rust 所有权",
    "kalman filter",
    '"device tree"',
    "tag:Rust lifetime",
)
type Index = QModelIndex | QPersistentModelIndex
type Opener = Callable[[Path], None]


def open_in_desktop(path: Path) -> None:
    """Open path with the program the desktop chose for it."""
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def read_markdown(doc: Document) -> str:
    """Return the Markdown of the post as it is in its file.

    The index holds the stripped text; the preview wants headings,
    code fences and links, so it reads the file and drops the front
    matter. If the file is gone it falls back to the indexed text.
    """
    try:
        text = doc.path.read_text(encoding="utf-8")
    except OSError:
        return doc.body
    return split_front_matter(text)[1]


def icon_pixmap(name: str, color: str, size: int) -> QPixmap:
    """Return the qtawesome icon name drawn in color at size px."""
    return icon(name, color).pixmap(size, size)


class Header(QFrame):
    """The header bar; it tells when it was painted for the first time."""

    painted = Signal()

    def __init__(self) -> None:
        """Make the frame that ``#header`` in the style sheet styles."""
        super().__init__()
        self.setObjectName("header")
        self._painted = False

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint, then emit ``painted`` once."""
        super().paintEvent(event)
        if not self._painted:
            self._painted = True
            self.painted.emit()


class StatePage(QWidget):
    """A centered icon, a line of text and optional example chips."""

    chosen = Signal(str)

    def __init__(
        self,
        icon: str,
        title: str,
        hint: str = "",
        examples: tuple[str, ...] = (),
    ) -> None:
        """Build the page; ``restyle`` paints the icon."""
        super().__init__()
        self.icon_name = icon
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("stateTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("stateHint")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setVisible(bool(hint))

        chips = QHBoxLayout()
        chips.setSpacing(SPACE_2)
        chips.addStretch(1)
        self.chips: list[QPushButton] = []
        for query in examples:
            chip = QPushButton(query)
            chip.setObjectName("exampleChip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, q=query: self.chosen.emit(q))
            chips.addWidget(chip)
            self.chips.append(chip)
        chips.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACE_3)
        layout.addStretch(2)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.hint_label)
        layout.addSpacing(SPACE_2)
        layout.addLayout(chips)
        layout.addStretch(3)

    def restyle(self, tokens: Tokens) -> None:
        """Draw the icon in the muted color of tokens."""
        self.icon_label.setPixmap(
            icon_pixmap(self.icon_name, tokens.muted, 72)
        )


class MainWindow(QMainWindow):
    """Search box, result cards, preview and status bar."""

    def __init__(
        self,
        catalog: Catalog,
        *,
        scheme: Scheme | None = None,
        opener: Opener = open_in_desktop,
        startup: QElapsedTimer | None = None,
    ) -> None:
        """Build the window and apply the theme.

        scheme None means the one of the system. opener opens a file
        (Ctrl+O); a test passes its own. startup is a timer started
        before the window was made; it is read when the header is
        painted for the first time and the result is ``first_paint_ms``.
        """
        super().__init__()
        self.catalog = catalog
        self.opener = opener
        self.startup = startup
        self.first_paint_ms: int | None = None
        self.latency_ms = 0.0  # request to the answer, in the UI thread
        self.apply_ms = 0.0  # what the UI thread then spent on it
        self.pool = QThreadPool.globalInstance()
        self._request_id = 0
        self._answered = 0  # the newest request id that was answered
        self._started = 0.0
        self._terms: set[str] = set()
        self._override = False
        self._searched = ""  # the text of the newest request
        self.scheme: Scheme = scheme or self.system_scheme()

        self.setWindowTitle("Sift")
        self.resize(WIDTH, HEIGHT)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(DEBOUNCE_MS)
        self.debounce.timeout.connect(self.search_now)

        self.model = ResultsModel()
        self._build()
        self._wire()
        self.tokens = apply_theme(self._app(), self.scheme)
        self._restyle()
        self.show_idle()

    # -- construction ---------------------------------------------------

    @staticmethod
    def _app() -> QApplication:
        """Return the running QApplication."""
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            raise RuntimeError("MainWindow needs a QApplication")
        return app

    @staticmethod
    def system_scheme() -> Scheme:
        """Return the color scheme the desktop asks for."""
        hints = QGuiApplication.styleHints()
        dark = hints.colorScheme() == Qt.ColorScheme.Dark
        return "dark" if dark else "light"

    def _build(self) -> None:
        """Create every widget and lay them out."""
        self.header = Header()
        self.app_name = QLabel("Sift")
        self.app_name.setObjectName("appName")
        self.doc_chip = QLabel(f"{self.catalog.n_docs} 篇")
        self.doc_chip.setObjectName("chip")
        brand = QWidget()
        brand.setObjectName("brand")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(SPACE_3)
        centered = Qt.AlignmentFlag.AlignVCenter
        brand_layout.addWidget(self.app_name, 0, centered)
        brand_layout.addWidget(self.doc_chip, 0, centered)
        brand.setFixedHeight(FIELD_HEIGHT)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            f"搜索 {self.catalog.n_docs} 篇文章，试试 rust 所有权 或 tag:Rust"
        )
        self.search_icon = QAction(self.search_edit)
        self.search_edit.addAction(
            self.search_icon, QLineEdit.ActionPosition.LeadingPosition
        )
        self.clear_action = QAction("清除", self.search_edit)
        self.clear_action.setVisible(False)
        self.search_edit.addAction(
            self.clear_action, QLineEdit.ActionPosition.TrailingPosition
        )
        self.banner = QLabel()
        self.banner.setObjectName("banner")
        self.banner.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.banner.hide()
        field = QVBoxLayout()  # the banner sits right under the field
        field.setContentsMargins(0, 0, 0, 0)
        field.setSpacing(SPACE_2)
        field.addWidget(self.search_edit)
        field.addWidget(self.banner)
        field_box = QWidget()
        field_box.setObjectName("fieldBox")
        field_box.setLayout(field)
        field_box.setMaximumWidth(FIELD_MAX_WIDTH)

        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setToolTip("切换浅色 / 深色")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout(self.header)
        row.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_3)
        row.setSpacing(SPACE_3)
        row.addWidget(brand, 0, Qt.AlignmentFlag.AlignTop)
        row.addSpacing(SPACE_5)
        row.addWidget(field_box, 1, Qt.AlignmentFlag.AlignTop)
        row.addStretch(0)
        row.addWidget(self.theme_button, 0, Qt.AlignmentFlag.AlignTop)

        self.busy = QProgressBar()
        self.busy.setObjectName("busy")
        self.busy.setTextVisible(False)
        self.busy.setRange(0, 1)
        self.busy.setValue(0)
        self.busy.setFixedHeight(2)

        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.delegate = ResultDelegate(self._initial_tokens(), self.list_view)
        self.list_view.setItemDelegate(self.delegate)
        self.list_view.setMouseTracking(True)
        self.list_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_view.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.list_view.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.list_view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.list_view.setFrameShape(QFrame.Shape.NoFrame)
        self.list_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.list_view.setSpacing(0)

        self.preview = PreviewBrowser()
        self.preview_hint = QLabel("选择一篇文章查看预览")
        self.preview_hint.setObjectName("stateHint")
        self.preview_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.preview_hint)
        self.preview_stack.addWidget(self.preview)
        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(1, 1, 1, 1)
        panel_layout.addWidget(self.preview_stack)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(SPACE_3)
        self.splitter.addWidget(self.list_view)
        self.splitter.addWidget(panel)
        body_width = WIDTH - 2 * SPACE_4
        left = body_width * RESULTS_SHARE // 100
        self.splitter.setSizes([left, body_width - left])
        self.splitter.setStretchFactor(0, RESULTS_SHARE)
        self.splitter.setStretchFactor(1, 100 - RESULTS_SHARE)

        self.start_page = StatePage(
            "mdi6.text-search", "输入关键词开始搜索", examples=EXAMPLES
        )
        self.empty_page = StatePage(
            "mdi6.file-search-outline",
            "没有找到匹配的文章",
            "换个关键词，或者去掉 tag: 之类的限定词",
        )
        self.body = QStackedWidget()
        self.body.addWidget(self.start_page)
        self.body.addWidget(self.empty_page)
        self.body.addWidget(self.splitter)

        holder = QWidget()
        holder.setObjectName("body")
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        holder_layout.addWidget(self.body)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.busy)
        layout.addWidget(holder, 1)
        self.setCentralWidget(central)

        self.status_label = QLabel()
        self.status_label.setContentsMargins(
            SPACE_4, SPACE_1, SPACE_4, SPACE_1
        )
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().setSizeGripEnabled(False)

    def _initial_tokens(self) -> Tokens:
        """Return the tokens of the starting scheme."""
        return TOKENS[self.scheme]

    def _wire(self) -> None:
        """Connect signals and make the shortcuts."""
        self.search_edit.textChanged.connect(self._on_text_changed)
        self.search_edit.returnPressed.connect(self._on_enter)
        self.search_edit.installEventFilter(self)
        self.clear_action.triggered.connect(self.search_edit.clear)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.header.painted.connect(self._on_first_paint)
        self.list_view.selectionModel().currentChanged.connect(
            self._on_current_changed
        )
        self.list_view.activated.connect(self._focus_preview)
        self.start_page.chosen.connect(self.search_example)
        QGuiApplication.styleHints().colorSchemeChanged.connect(
            self._on_system_scheme
        )
        for keys, slot in (
            ("Ctrl+K", self.focus_search),
            ("Ctrl+O", self.open_current),
            ("Esc", self.clear_search),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(slot)

    # -- theme ----------------------------------------------------------

    def set_scheme(self, scheme: Scheme, *, manual: bool = False) -> None:
        """Switch to scheme; manual stops following the system."""
        if manual:
            self._override = True
        self.scheme = scheme
        self.tokens = apply_theme(self._app(), scheme)
        self._restyle()

    def toggle_theme(self) -> None:
        """Switch light and dark for the rest of the session."""
        self.set_scheme(
            "light" if self.scheme == "dark" else "dark", manual=True
        )

    def _on_system_scheme(self, _scheme: Qt.ColorScheme) -> None:
        """Follow the desktop unless the user chose a theme."""
        if not self._override:
            self.set_scheme(self.system_scheme())

    def _restyle(self) -> None:
        """Repaint what the style sheet does not reach: icons, cards."""
        t = self.tokens
        self.search_icon.setIcon(icon("mdi6.magnify", color=t.muted))
        self.clear_action.setIcon(icon("mdi6.close-circle", color=t.muted))
        moon_or_sun = (
            "mdi6.weather-night"
            if self.scheme == "light"
            else "mdi6.white-balance-sunny"
        )
        self.theme_button.setIcon(icon(moon_or_sun, color=t.text))
        self.delegate.set_tokens(t)
        self.start_page.restyle(t)
        self.empty_page.restyle(t)
        self.list_view.doItemsLayout()
        self.list_view.viewport().update()
        self._show_row(self.current_row())

    # -- search ---------------------------------------------------------

    def _on_text_changed(self, text: str) -> None:
        """Restart the debounce timer, or go idle on an empty box."""
        self.clear_action.setVisible(bool(text))
        if text.strip():
            self.debounce.start()
        else:
            self.debounce.stop()
            self._request_id += 1  # whatever is still running is stale
            self._answered = self._request_id
            self.busy.setRange(0, 1)
            self.show_idle()

    @property
    def searching(self) -> bool:
        """Return True while the newest request has no answer yet."""
        return self._answered != self._request_id

    def search_now(self) -> None:
        """Start a search for the text of the box, without waiting."""
        self.debounce.stop()
        text = self.search_edit.text().strip()
        if not text:
            return
        self._request_id += 1
        self._searched = text
        self._started = time.perf_counter()
        self.busy.setRange(0, 0)
        worker = SearchWorker(self.catalog, text, self._request_id)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self.pool.start(worker)

    def search_example(self, query: str) -> None:
        """Put an example query in the box and search it at once."""
        self.search_edit.setText(query)
        self.search_now()

    def _on_finished(self, result: SearchResult, request_id: int) -> None:
        """Show the answer, unless a newer request has been made."""
        if request_id != self._request_id:
            return
        self._answered = request_id
        self.latency_ms = (time.perf_counter() - self._started) * 1000
        self.busy.setRange(0, 1)
        self.banner.hide()
        applying = time.perf_counter()
        self._terms = self.catalog.terms(self._searched)
        cards = make_cards(result, self.catalog.document)
        self.model.set_cards(cards)
        status = f"{result.total} 条结果 · {result.took_ms:.1f} ms"
        if self.catalog.logs_queries:
            status += " · 查询日志已记录"
        self.status_label.setText(status)
        if cards:
            self.body.setCurrentWidget(self.splitter)
            self.list_view.setCurrentIndex(self.model.index(0))
        else:
            self.body.setCurrentWidget(self.empty_page)
            self._show_row(-1)
        self.apply_ms = (time.perf_counter() - applying) * 1000

    def _on_failed(self, text: str, request_id: int) -> None:
        """Show the error under the search field."""
        if request_id != self._request_id:
            return
        self._answered = request_id
        self.latency_ms = (time.perf_counter() - self._started) * 1000
        self.busy.setRange(0, 1)
        self.banner.setText(text)
        self.banner.show()
        self.model.set_cards([])
        self.body.setCurrentWidget(self.start_page)
        self.status_label.setText("查询有误")
        self._show_row(-1)

    def show_idle(self) -> None:
        """Show the start page: nothing was asked yet."""
        self.banner.hide()
        self.model.set_cards([])
        self.body.setCurrentWidget(self.start_page)
        self.status_label.setText(f"共 {self.catalog.n_docs} 篇文章")
        self._show_row(-1)

    # -- selection and preview -------------------------------------------

    def current_row(self) -> int:
        """Return the selected row, -1 if there is none."""
        return self.list_view.currentIndex().row()

    def _on_current_changed(self, current: Index, _previous: Index) -> None:
        """Show the post of the row that became current."""
        self._show_row(current.row() if current.isValid() else -1)

    def _show_row(self, row: int) -> None:
        """Fill the preview with the post of row, or empty it."""
        card = self.model.card(row)
        if card is None:
            self.preview.clear_post()
            self.preview_stack.setCurrentWidget(self.preview_hint)
            return
        doc = self.catalog.document(card.doc_id)
        meta = "  ·  ".join(
            part
            for part in (card.date, card.category, ", ".join(doc.tags))
            if part
        )
        self.preview.show_post(
            card.title, meta, read_markdown(doc), self._terms, self.tokens
        )
        self.preview_stack.setCurrentWidget(self.preview)

    def move_selection(self, step: int) -> None:
        """Move the selection by step rows, stopping at the ends."""
        count = self.model.rowCount()
        if not count:
            return
        row = min(max(self.current_row() + step, 0), count - 1)
        self.list_view.setCurrentIndex(self.model.index(row))

    # -- keys -----------------------------------------------------------

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Let Up and Down in the search box move the selection."""
        if (
            watched is self.search_edit
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)
        ):
            step = -1 if event.key() == Qt.Key.Key_Up else 1
            self.move_selection(step)
            return True
        return super().eventFilter(watched, event)

    def focus_search(self) -> None:
        """Put the cursor in the search box, text selected."""
        self.search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search_edit.selectAll()

    def clear_search(self) -> None:
        """Empty the box and go back to the start page."""
        self.search_edit.clear()
        self.search_edit.setFocus()

    def _on_enter(self) -> None:
        """Search now if the text is new, else go into the preview."""
        text = self.search_edit.text().strip()
        if self.debounce.isActive() or text != self._searched:
            self.search_now()
        elif self.model.rowCount():
            self._focus_preview()

    def _focus_preview(self, _index: Index | None = None) -> None:
        """Move the keyboard focus to the preview, to scroll it."""
        if self.preview_stack.currentWidget() is self.preview:
            self.preview.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def open_current(self) -> None:
        """Open the file of the selected post (``sift open``)."""
        card = self.model.card(self.current_row())
        if card is not None:
            self.opener(card.path)

    # -- life cycle -----------------------------------------------------

    def _on_first_paint(self) -> None:
        """Read the startup timer once."""
        if self.startup is not None and self.first_paint_ms is None:
            self.first_paint_ms = self.startup.elapsed()

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        """Wait for a running search: it must not outlive the window."""
        self.debounce.stop()
        self.pool.waitForDone(2000)
        super().closeEvent(event)

"""The search window of Sift in tkinter: ``sift gui --tk``.

Tk is a Tcl interpreter that lives inside the Python process; the
widgets are Tcl commands and ``tkinter`` sends them strings. The
window here is ttk with the Sun Valley theme (``sv-ttk``), light or
dark as ``darkdetect`` reports, and a button to switch.

The layout is a grid with 16 px between the parts::

    +--------------------------------------------+
    | [ search entry                ] [搜索] [深色] |
    | +---------------+ +----------------------+ |
    | | 排名 分数 标题  | | preview (Text)       | |
    | | results       | |                      | |
    | +---------------+ +----------------------+ |
    | N 条结果，X ms                               |
    +--------------------------------------------+

``SearchWindow`` only draws. What a click or a key means is in
``sift.gui.controller``: the window is its ``View``. A search runs on
a worker thread; the answer comes back through a ``queue.Queue`` that
``root.after(30, ...)`` polls on the UI thread, because a Tk widget
may only be touched from the thread that made it.

``darkdetect`` has no type information and ``sv_ttk`` is used only
through ``apply_sun_valley``: the two small functions at the top are
the whole contact surface with them.
"""

import contextlib
import io
import tkinter as tk
from collections.abc import Sequence
from tkinter import font, ttk
from typing import Literal, Protocol

import darkdetect
import sv_ttk

from sift.errors import SiftError
from sift.gui.controller import (
    Backend,
    Controller,
    Preview,
    Row,
)

type Theme = Literal["light", "dark"]

PAD = 16
POLL_MS = 30
WIDTH = 1100
HEIGHT = 700
LATIN_FONT = "Inter"
MONO_FONT = "JetBrains Mono"
FONT_SIZE = 11
ERROR_COLOR: dict[Theme, str] = {"light": "#c42b1c", "dark": "#ff99a4"}
THEME_NAMES: dict[Theme, str] = {"light": "浅色", "dark": "深色"}


def detect_theme() -> Theme:
    """Return the theme of the desktop, "light" if it cannot tell.

    darkdetect asks the desktop (gsettings on Linux). Under Xvfb, in
    a container or without gsettings it answers "Light" or None.
    """
    name = str(darkdetect.theme())
    if name.lower() == "dark":
        return "dark"
    return "light"


def apply_sun_valley(root: tk.Tk, theme: Theme) -> None:
    """Load the Sun Valley theme into root and switch to theme."""
    sv_ttk.set_theme(theme, root)


class ScrollCommand(Protocol):
    """What a scrollbar calls: ``moveto F`` or ``scroll N what``."""

    def __call__(self, *args: str) -> None:
        """Scroll as the arguments say."""
        ...


def scroll_command(widget: tk.Text | ttk.Treeview) -> ScrollCommand:
    """Return the ``command`` of a scrollbar that drives widget.

    Tk calls it with ``moveto FRACTION`` (the thumb was dragged) or
    ``scroll N units|pages`` (an arrow or the trough was clicked).
    ``widget.yview`` does the same, but its overloads are untyped.
    """

    def command(*args: str) -> None:
        match args:
            case ("moveto", fraction):
                widget.yview_moveto(float(fraction))
            case ("scroll", number, "pages"):
                widget.yview_scroll(int(number), "pages")
            case ("scroll", number, _):
                widget.yview_scroll(int(number), "units")
            case _:
                pass  # Tk sends no other form

    return command


class Palette:
    """The colors of one theme, read from the Tcl side of sv-ttk.

    sv-ttk keeps them in Tcl arrays such as
    ``::ttk::theme::sv_dark::colors(-accent)``. Reading them there
    means the preview and the stripes follow the theme without a copy
    of its numbers in Python.
    """

    def __init__(self, root: tk.Tk, theme: Theme) -> None:
        """Read bg, fg and accent of theme and mix the others."""
        array = f"::ttk::theme::sv_{theme}::colors"
        self.theme = theme
        self.bg = root.tk.eval(f"set {array}(-bg)")
        self.fg = root.tk.eval(f"set {array}(-fg)")
        self.accent = root.tk.eval(f"set {array}(-accent)")
        self.stripe = mix(root, self.bg, self.fg, 0.05)
        self.border = mix(root, self.bg, self.fg, 0.2)
        self.muted = mix(root, self.fg, self.bg, 0.4)
        self.hit = mix(root, self.bg, self.accent, 0.3)
        self.error = ERROR_COLOR[theme]


def mix(root: tk.Misc, base: str, top: str, amount: float) -> str:
    """Return the color amount of the way from base to top.

    Both are Tk color names; the result is ``#rrggbb``. The
    interpreter of root converts the names.
    """
    r1, g1, b1 = root.winfo_rgb(base)
    r2, g2, b2 = root.winfo_rgb(top)

    def channel(one: int, two: int) -> int:
        return round((one + (two - one) * amount) / 257)

    return f"#{channel(r1, r2):02x}{channel(g1, g2):02x}{channel(b1, b2):02x}"


class SearchWindow:
    """The window: widgets, theme, fonts. It implements ``View``."""

    def __init__(
        self, root: tk.Tk, backend: Backend, *, theme: Theme | None = None
    ) -> None:
        """Build the widgets in root and start in theme.

        theme defaults to what darkdetect reports.
        """
        self.root = root
        self.controller = Controller(backend, self)
        self.query = tk.StringVar(root)
        self.status_text = tk.StringVar(root)
        self.theme: Theme = theme or detect_theme()
        self._error = False
        self._poll_id: str | None = None
        apply_sun_valley(root, self.theme)
        self.palette = Palette(root, self.theme)
        self.body_font = self._make_fonts()
        self._build()
        self._style()
        self.entry.focus_set()

    # -- fonts ---------------------------------------------------------

    def _make_fonts(self) -> font.Font:
        """Name the fonts and point the theme's fonts at Inter.

        A Tk font names one family. A character that Inter lacks (all
        of CJK) is drawn by Tk from another family that fontconfig
        picks, here Noto Sans CJK SC, glyph by glyph.
        """
        root = self.root
        body = font.Font(
            root, name="SiftBody", family=LATIN_FONT, size=FONT_SIZE
        )
        font.Font(
            root,
            name="SiftTitle",
            family=LATIN_FONT,
            size=FONT_SIZE + 4,
            weight="bold",
        )
        font.Font(root, name="SiftMono", family=MONO_FONT, size=FONT_SIZE - 1)
        for name in (
            "TkDefaultFont",
            "TkTextFont",
            "TkHeadingFont",
            "TkMenuFont",
            "SunValleyBodyFont",
            "SunValleyBodyStrongFont",
        ):
            font.nametofont(name, root).configure(
                family=LATIN_FONT, size=FONT_SIZE
            )
        return body

    # -- widgets -------------------------------------------------------

    def _build(self) -> None:
        """Create the widgets and grid them."""
        root = self.root
        root.title("Sift")
        root.geometry(f"{WIDTH}x{HEIGHT}")
        root.minsize(720, 480)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main = ttk.Frame(root, padding=PAD)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=2, uniform="panes")
        main.columnconfigure(1, weight=3, uniform="panes")
        main.rowconfigure(1, weight=1)

        bar = ttk.Frame(main)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, PAD))
        bar.columnconfigure(0, weight=1)
        self.entry = ttk.Entry(bar, textvariable=self.query, font="SiftBody")
        self.entry.grid(row=0, column=0, sticky="ew")
        self.button = ttk.Button(
            bar, text="搜索", style="Accent.TButton", command=self.submit
        )
        self.button.grid(row=0, column=1, padx=(PAD, 0))
        self.toggle = ttk.Button(bar, command=self.toggle_theme)
        self.toggle.grid(row=0, column=2, padx=(PAD, 0))

        left = ttk.Frame(main)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, PAD // 2))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            left,
            columns=("rank", "score", "title"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("rank", text="排名")
        self.tree.heading("score", text="分数")
        self.tree.heading("title", text="标题")
        self.tree.column("rank", width=64, stretch=False, anchor="e")
        self.tree.column("score", width=80, stretch=False, anchor="e")
        self.tree.column("title", width=200, stretch=True, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_bar = ttk.Scrollbar(left, command=scroll_command(self.tree))
        tree_bar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_bar.set)

        right = ttk.Frame(main)
        right.grid(row=1, column=1, sticky="nsew", padx=(PAD // 2, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        line = self.body_font.metrics("linespace")
        self.preview = tk.Text(
            right,
            wrap="word",
            state="disabled",
            font=self.body_font,
            spacing2=line // 2,
            padx=PAD,
            pady=PAD,
            borderwidth=0,
            insertwidth=0,
            highlightthickness=1,
            cursor="arrow",
            width=10,
            height=10,
        )
        self.preview.grid(row=0, column=0, sticky="nsew")
        text_bar = ttk.Scrollbar(right, command=scroll_command(self.preview))
        text_bar.grid(row=0, column=1, sticky="ns")
        self.preview.configure(yscrollcommand=text_bar.set)

        self.status = ttk.Label(
            main, textvariable=self.status_text, font="SiftBody"
        )
        self.status.grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(PAD, 0)
        )

        self.entry.bind("<Return>", lambda event: self.submit())
        self.tree.bind("<<TreeviewSelect>>", lambda event: self._selected())

    def _style(self) -> None:
        """Apply the palette to the widgets that sv-ttk does not own."""
        p = self.palette
        self.toggle.configure(text=THEME_NAMES[self._other()] + "模式")
        self.preview.configure(
            background=p.bg,
            foreground=p.fg,
            highlightbackground=p.border,
            highlightcolor=p.border,
            selectbackground=p.accent,
            selectforeground=p.bg,
        )
        self.preview.tag_configure("hit", background=p.hit)
        self.preview.tag_configure(
            "title",
            font="SiftTitle",
            spacing3=self.body_font.metrics("linespace") // 4,
        )
        self.preview.tag_configure("meta", foreground=p.muted, spacing3=PAD)
        self.tree.tag_configure("even", background=p.bg)
        self.tree.tag_configure("odd", background=p.stripe)
        self._style_status()

    def _style_status(self) -> None:
        """Color the status line: red and monospaced after an error."""
        if self._error:
            self.status.configure(
                foreground=self.palette.error, font="SiftMono"
            )
        else:
            self.status.configure(foreground="", font="SiftBody")

    def _other(self) -> Theme:
        """Return the theme that the toggle button switches to."""
        return "dark" if self.theme == "light" else "light"

    # -- actions -------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        """Switch to theme: sv-ttk first, then what depends on it."""
        self.theme = theme
        apply_sun_valley(self.root, theme)
        self.palette = Palette(self.root, theme)
        self._style()

    def toggle_theme(self) -> None:
        """Switch between the light and the dark theme."""
        self.set_theme(self._other())

    def submit(self) -> None:
        """Search for the text of the entry, and poll for the answer."""
        if self.controller.submit(self.query.get()):
            self._schedule_poll()

    def _schedule_poll(self) -> None:
        """Poll the controller in POLL_MS ms, unless that is planned."""
        if self._poll_id is None:
            self._poll_id = self.root.after(POLL_MS, self._tick)

    def _tick(self) -> None:
        """Apply the answers; poll again while a search is pending."""
        self._poll_id = None
        self.controller.poll()
        if self.controller.pending:
            self._schedule_poll()

    def _selected(self) -> None:
        """Show the preview of the selected row."""
        chosen = self.tree.selection()
        if chosen:
            self.controller.select(int(chosen[0]))

    # -- View ----------------------------------------------------------

    def show_busy(self, busy: bool) -> None:
        """Disable the search button while a search runs."""
        self.button.state(["disabled"] if busy else ["!disabled"])

    def show_results(self, rows: Sequence[Row]) -> None:
        """Fill the table; odd rows carry the stripe tag."""
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(rows):
            stripe = "odd" if index % 2 else "even"
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=row.cells(),
                tags=(stripe,),
            )

    def select_row(self, index: int | None) -> None:
        """Select a row and scroll to it."""
        if index is None:
            self.tree.selection_set(())
            return
        iid = str(index)
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.tree.see(iid)

    def show_status(self, text: str, *, error: bool) -> None:
        """Set the status line."""
        self._error = error
        self.status_text.set(text)
        self._style_status()

    def show_preview(self, preview: Preview | None) -> None:
        """Replace the text of the preview; hits carry the hit tag."""
        text = self.preview
        text.configure(state="normal")
        text.delete("1.0", "end")
        if preview is not None:
            text.insert("end", preview.title + "\n", ("title",))
            text.insert("end", preview.meta + "\n", ("meta",))
            for part, is_hit in preview.parts():
                text.insert("end", part, ("hit",) if is_hit else ())
        text.configure(state="disabled")
        text.yview_moveto(0)


def run(backend: Backend, *, theme: Theme | None = None) -> None:
    """Open the window and run the Tk main loop until it is closed.

    Raise SiftError if there is no display to open the window on.
    _tkinter prints its own "Tk_Init error" line before it raises;
    it is swallowed so that the error is said once.
    """
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            root = tk.Tk()
    except tk.TclError as error:
        raise SiftError(f"cannot open a display: {error}") from None
    SearchWindow(root, backend, theme=theme)
    root.mainloop()

"""Tests of the Tk window; they need a display.

``tests/test_tk_window.py`` runs this directory under Xvfb. The
conftest leaves it out of a normal run, so these tests never open a
window on the screen of whoever runs pytest.
"""

import tkinter as tk
from collections.abc import Iterator

import pytest

from sift.gui.controller import IndexBackend
from sift.gui.tk_app import SearchWindow, Theme, detect_theme
from sift.search import Searcher


@pytest.fixture
def root() -> Iterator[tk.Tk]:
    try:
        window = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"no display: {error}")
    yield window
    window.destroy()


@pytest.fixture
def window(root: tk.Tk, searcher: Searcher) -> SearchWindow:
    return SearchWindow(root, IndexBackend(searcher, 5), theme="light")


def wait_for_answer(window: SearchWindow) -> None:
    for _ in range(400):
        window.root.update()
        if window.controller.pending == 0 and window.tree.get_children():
            return
        window.root.after(5)
    raise AssertionError("no answer")


def test_window_layout_and_strings(window: SearchWindow) -> None:
    window.root.update()
    assert window.root.winfo_width() == 1100
    assert window.root.winfo_height() == 700
    assert window.button.cget("text") == "搜索"
    assert window.button.cget("style") == "Accent.TButton"
    headings = [
        window.tree.heading(c, "text") for c in ("rank", "score", "title")
    ]
    assert headings == ["排名", "分数", "标题"]
    assert "headings" in str(window.tree.cget("show"))
    assert window.preview.cget("state") == "disabled"
    assert window.entry.grid_info()["sticky"] == "ew"


def test_return_searches_and_fills_every_part(window: SearchWindow) -> None:
    window.query.set("chain")
    window.root.update()
    window.entry.focus_force()
    window.root.update()
    window.entry.event_generate("<Return>")
    wait_for_answer(window)
    (iid,) = window.tree.get_children()
    assert window.tree.item(iid, "values")[2] == "Fixing a bicycle chain"
    assert window.tree.item(iid, "tags") in (("even",), "even")
    assert window.status_text.get().startswith("1 条结果，")
    assert window.tree.selection() == (iid,)
    text = window.preview.get("1.0", "end")
    assert text.startswith("Fixing a bicycle chain\n")
    hits = window.preview.tag_ranges("hit")
    assert hits
    assert window.preview.get(hits[0], hits[1]).lower() == "chain"
    assert window.button.instate(["!disabled"])


def test_stripes_alternate(window: SearchWindow) -> None:
    window.query.set("tea OR bicycle OR chain")
    window.submit()
    wait_for_answer(window)
    tags = [window.tree.item(i, "tags") for i in window.tree.get_children()]
    flat = [t[0] if isinstance(t, tuple) else t for t in tags]
    assert flat[:4] == ["even", "odd", "even", "odd"][: len(flat[:4])]
    assert len(flat) >= 2


def test_syntax_error_is_red_with_a_caret(window: SearchWindow) -> None:
    window.query.set("(tea")
    window.submit()
    for _ in range(400):
        window.root.update()
        if window.controller.pending == 0:
            break
        window.root.after(5)
    text = window.status_text.get()
    assert text.splitlines()[-1].strip() == "^"
    colour = str(window.status.cget("foreground"))
    assert colour == window.palette.error == "#c42b1c"


def test_toggle_switches_theme_and_colors(window: SearchWindow) -> None:
    before = str(window.preview.cget("background"))
    window.toggle.invoke()
    assert window.theme == "dark"
    assert str(window.preview.cget("background")) != before
    assert "浅色" in str(window.toggle.cget("text"))
    window.toggle.invoke()
    assert window.theme == "light"
    assert str(window.preview.cget("background")) == before


def test_hit_color_is_a_mix_of_the_accent(window: SearchWindow) -> None:
    p = window.palette
    assert p.accent == "#005fb8"
    assert p.hit not in (p.bg, p.accent)
    assert str(window.preview.tag_cget("hit", "background")) == p.hit


def test_polling_stops_when_idle(window: SearchWindow) -> None:
    window.query.set("chain")
    window.submit()
    wait_for_answer(window)
    window.root.update()
    assert window.controller.pending == 0
    assert window._poll_id is None


def test_fonts_are_inter_with_a_cjk_fallback(window: SearchWindow) -> None:
    import tkinter.font as tkfont

    body = tkfont.nametofont("SiftBody", window.root)
    assert body.actual("family") == "Inter"
    assert body.actual("size") == 11
    assert body.measure("所有权") > body.measure("abc")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_both_themes_build(
    root: tk.Tk, searcher: Searcher, theme: Theme
) -> None:
    made = SearchWindow(root, IndexBackend(searcher), theme=theme)
    assert made.theme == theme


def test_detect_theme_is_light_or_dark() -> None:
    assert detect_theme() in ("light", "dark")

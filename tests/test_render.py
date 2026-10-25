"""Tests for sift.render: the rich output and its plain fallback."""

import io
import sys
from pathlib import Path

import pytest
from rich.console import Console

from sift import render
from sift.search import Hit, SearchResult
from sift.snippet import render_plain

PARTS = [("see the ", False), ("[chain]", True), (" and [tool]", False)]


def result_of(*parts_lists: list[tuple[str, bool]]) -> SearchResult:
    """Return a result with one hit per snippet."""
    hits = [
        Hit(i, f"Title {i}", Path(f"posts/p{i}.md"), 2.5 - i, parts)
        for i, parts in enumerate(parts_lists)
    ]
    return SearchResult("chain", len(hits), 1.234, hits)


class Stream(io.StringIO):
    """A text stream that says whether it is a terminal."""

    def __init__(self, tty: bool) -> None:
        super().__init__()
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start with a terminal-friendly environment."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")


def test_a_terminal_wants_rich() -> None:
    assert render.wants_rich(Stream(tty=True))


def test_a_pipe_does_not_want_rich() -> None:
    assert not render.wants_rich(Stream(tty=False))


@pytest.mark.parametrize("value", ["1", "yes", "0", "false"])
def test_no_color_turns_rich_off(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("NO_COLOR", value)
    assert not render.wants_rich(Stream(tty=True))


def test_empty_no_color_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "")
    assert render.wants_rich(Stream(tty=True))


def test_a_dumb_terminal_does_not_want_rich(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TERM", "dumb")
    assert not render.wants_rich(Stream(tty=True))


def test_stdout_console_is_none_in_a_pipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdout", Stream(tty=False))
    assert render.stdout_console() is None
    monkeypatch.setattr(sys, "stdout", Stream(tty=True))
    assert isinstance(render.stdout_console(), Console)


def test_snippet_text_marks_only_the_matches() -> None:
    text = render.snippet_text(PARTS)
    assert text.plain == "see the [chain] and [tool]"
    (span,) = text.spans
    assert text.plain[span.start : span.end] == "[chain]"
    assert span.style == render.HIT_STYLE


def test_markup_in_a_post_is_not_interpreted() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, width=60, force_terminal=False)
    console.print(render.snippet_text([("a [bold]b[/bold] c", False)]))
    assert buffer.getvalue() == "a [bold]b[/bold] c\n"


def record(result: SearchResult, n_docs: int = 8) -> tuple[str, Console]:
    """Print the result on a recording terminal; return text and console."""
    console = Console(
        file=io.StringIO(),
        width=70,
        force_terminal=True,
        color_system="truecolor",
        record=True,
    )
    render.print_hits(result, n_docs, 12.0, console)
    return console.export_text(clear=False), console


def test_the_table_has_one_row_per_hit_and_the_footer() -> None:
    text, _ = record(result_of(PARTS, [("only ", False), ("tool", True)]))
    assert "Title 0" in text and "Title 1" in text
    assert "posts/p0.md" in text and "posts/p1.md" in text
    assert "see the [chain] and [tool]" in text
    assert text.count("╭") == 1
    last = text.rstrip().splitlines()[-1]
    assert last == (
        "2 hits in 8 files: index opened in 12.0 ms, query took 1.234 ms"
    )


def test_the_matches_are_drawn_highlighted() -> None:
    _, console = record(result_of(PARTS))
    styled = console.export_text(styles=True)
    assert "\x1b[" in styled
    # the highlight wraps the match and nothing else of the snippet
    assert "\x1b[1;30;43m[chain]\x1b[0m" in styled


def test_no_hits_prints_only_the_footer() -> None:
    text, _ = record(result_of())
    assert text.strip() == (
        "0 hits in 8 files: index opened in 12.0 ms, query took 1.234 ms"
    )


def test_plain_output_is_the_text_of_chapter_18(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = result_of(PARTS)
    render.print_hits(result, 8, 12.0, None)
    assert capsys.readouterr().out == (
        " 1    2.500  posts/p0.md\n"
        "    Title 0\n"
        f"    {render_plain(PARTS)}\n"
        "1 hits in 8 files: index opened in 12.0 ms, query took 1.234 ms\n"
    )


def test_the_summary_line_has_no_timings() -> None:
    assert render.summary_line(result_of(PARTS), 8) == "1 hits in 8 files"


def test_progress_is_none_off_a_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stderr", Stream(tty=False))
    with render.index_progress() as progress:
        assert progress is None


def test_progress_draws_on_stderr_and_leaves_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = Stream(tty=True)
    monkeypatch.setattr(sys, "stderr", stderr)
    with render.index_progress() as progress:
        assert progress is not None
        progress(0, 10)
        progress(5, 10)
        progress(10, 10)
    assert "\x1b" in stderr.getvalue()
    assert "10/10" in stderr.getvalue()


def test_progress_that_is_never_called_draws_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = Stream(tty=True)
    monkeypatch.setattr(sys, "stderr", stderr)
    with render.index_progress() as progress:
        assert progress is not None
    assert "10/10" not in stderr.getvalue()
    assert "indexing" not in stderr.getvalue().replace("\x1b[?25l", "")


def test_install_traceback_replaces_the_excepthook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "excepthook", sys.__excepthook__)
    render.install_traceback()
    assert sys.excepthook is not sys.__excepthook__


def test_print_traceback_shows_the_exception_on_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = Stream(tty=False)
    monkeypatch.setattr(sys, "stderr", stderr)
    try:
        raise ValueError("boom")
    except ValueError:
        render.print_traceback()
    assert "ValueError" in stderr.getvalue()
    assert "boom" in stderr.getvalue()

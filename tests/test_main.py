"""Tests for the command line in sift.__main__."""

import pytest

import sift.__main__ as cli
from sift.errors import ConfigError


@pytest.fixture
def mini_cli(monkeypatch: pytest.MonkeyPatch, mini_root):
    """Point the CLI at the fixture posts instead of corpus/posts."""
    monkeypatch.setattr(cli, "CORPUS", mini_root)
    return cli


def test_search_prints_ranked_hits(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.dispatch(["search", "chain", "tool"])
    out = capsys.readouterr().out
    assert "bicycle-repair.md" in out
    assert "Fixing a bicycle chain" in out
    assert "[chain]" in out.lower()
    assert "1 hits in 8 files" in out


def test_search_words_are_joined_into_one_query(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.dispatch(["search", '"chain', 'tool"'])
    assert "1 hits" in capsys.readouterr().out


def test_stats(mini_cli, capsys: pytest.CaptureFixture[str]) -> None:
    mini_cli.dispatch(["stats"])
    out = capsys.readouterr().out
    assert "documents: 8" in out
    assert "vocabulary: " in out


def test_bench_runs_every_query(
    mini_cli,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    queries = tmp_path / "queries.txt"
    queries.write_text("chain\n\n编译\n", encoding="utf-8")
    monkeypatch.setattr(mini_cli, "QUERIES", queries)
    mini_cli.dispatch(["bench"])
    out = capsys.readouterr().out
    assert "total for 2 queries" in out


@pytest.mark.parametrize("args", [[], ["search"], ["stats", "x"], ["nope"]])
def test_bad_usage_exits_with_the_usage_text(args: list[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        cli.dispatch(args)
    assert caught.value.code == cli.USAGE


def run_main(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    """Run main() with sys.argv set; return the exit status."""
    monkeypatch.setattr("sys.argv", ["sift", *args])
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert isinstance(caught.value.code, int)
    return caught.value.code


def test_query_syntax_error_exits_3_with_a_caret(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_main(monkeypatch, "search", "a AND") == 3
    err = capsys.readouterr().err
    assert err == "expected a term\n  a AND\n       ^\n"


def test_sift_error_exits_1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def boom(args: list[str]) -> None:
        raise ConfigError("bad setting")

    monkeypatch.setattr(cli, "dispatch", boom)
    assert run_main(monkeypatch, "stats") == 1
    assert capsys.readouterr().err == "error: bad setting\n"


def test_group_of_sift_errors_exits_1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def boom(args: list[str]) -> None:
        raise ExceptionGroup(
            "2 files failed", [ConfigError("a"), ConfigError("b")]
        )

    monkeypatch.setattr(cli, "dispatch", boom)
    assert run_main(monkeypatch, "stats") == 1
    assert capsys.readouterr().err == "error: 2 files failed\n  a\n  b\n"


def test_group_with_a_bug_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(args: list[str]) -> None:
        raise ExceptionGroup("mixed", [ConfigError("a"), KeyError("b")])

    monkeypatch.setattr(cli, "dispatch", boom)
    monkeypatch.setattr("sys.argv", ["sift", "stats"])
    with pytest.raises(ExceptionGroup, match="mixed"):
        cli.main()

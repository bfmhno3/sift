"""Tests for the command line in sift.cli.

Most tests run the typer app with typer's CliRunner (``invoke``): the
runner returns the exit code, stdout and stderr of one command, the
same three things a shell sees. The tests of ``main`` and of the
server commands run the real thing.
"""

import asyncio
import json
import logging
import os
import pstats
import shutil
import signal
import socket
import subprocess
import sys
import urllib.request
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
import typer.main
from typer.testing import CliRunner, Result

import sift
import sift.cli as cli
from sift.document import Document
from sift.errors import ConfigError, SiftError
from sift.storage.db import recent_queries

# A wide terminal: a rich error panel wraps at 80 columns by default,
# and the tests look for whole phrases.
RUNNER = CliRunner(env={"COLUMNS": "200"})


@pytest.fixture(autouse=True)
def no_sift_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test with SIFT_INDEX unset."""
    monkeypatch.delenv("SIFT_INDEX", raising=False)


@pytest.fixture(autouse=True)
def plain_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep typer from forcing colour codes (GITHUB_ACTIONS, FORCE_COLOR)."""
    monkeypatch.setattr("typer.rich_utils.FORCE_TERMINAL", None)


@pytest.fixture(autouse=True)
def restore_sift_logger() -> Iterator[None]:
    """Give the sift logger back as it was: commands replace its handler."""
    logger = logging.getLogger("sift")
    handlers, level = logger.handlers[:], logger.level
    yield
    logger.handlers[:] = handlers
    logger.setLevel(level)


def invoke(*args: str, input: str | None = None) -> Result:
    """Run ``sift ARGS`` in process; return the runner's Result."""
    return RUNNER.invoke(cli.app, list(args), input=input)


def ok(*args: str, input: str | None = None) -> Result:
    """Run ``sift ARGS`` and check that it exits 0."""
    result = invoke(*args, input=input)
    assert result.exit_code == 0, result.output
    return result


def code_of(*args: str) -> int:
    """Run ``sift ARGS``; return the exit code."""
    return invoke(*args).exit_code


@pytest.fixture
def mini_cli(
    monkeypatch: pytest.MonkeyPatch, mini_root: Path, tmp_path: Path
) -> None:
    """Work in a temp dir with a sift.toml and an index of the mini posts."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sift.toml").write_text(
        f'[index]\ncorpus = "{mini_root}"\npath = "{tmp_path / "idx"}"\n',
        encoding="utf-8",
    )
    ok("index")


def test_search_prints_ranked_hits(mini_cli) -> None:
    out = ok("search", "chain", "tool").stdout
    assert "bicycle-repair.md" in out
    assert "Fixing a bicycle chain" in out
    assert "[chain]" in out.lower()
    assert "1 hits in 8 files: index opened in" in out


def test_search_words_are_joined_into_one_query(mini_cli) -> None:
    assert "1 hits" in ok("search", '"chain', 'tool"').stdout


def test_search_limit(mini_cli) -> None:
    out = ok("search", "--limit", "1", "tea", "OR", "bicycle").stdout
    assert out.count(".md") == 1


def test_search_limit_accepts_the_maximum(mini_cli) -> None:
    out = ok("search", "--limit", "100", "tea", "OR", "bicycle").stdout
    assert out.count(".md") >= 1


def test_search_json(mini_cli) -> None:
    data = json.loads(ok("search", "--json", "chain", "tool").stdout)
    assert data["total"] == 1
    assert data["hits"][0]["path"].endswith("bicycle-repair.md")
    assert data["hits"][0]["title"] == "Fixing a bicycle chain"


def test_search_json_has_the_documented_keys(mini_cli) -> None:
    data = json.loads(ok("search", "--json", "chain").stdout)
    assert list(data) == ["query", "total", "took_ms", "hits"]
    assert list(data["hits"][0]) == [
        "doc_id",
        "title",
        "path",
        "score",
        "snippet",
    ]
    assert "[chain]" in data["hits"][0]["snippet"].lower()


def test_search_no_log_does_not_log(mini_cli, tmp_path: Path) -> None:
    out = ok("search", "--no-log", "chain").stdout
    assert "hits in 8 files" in out
    assert recent_queries(tmp_path / "idx" / "sift.db") == []


def test_search_logs_the_query(mini_cli, tmp_path: Path) -> None:
    ok("search", "chain", "tool")
    ok("search", "--json", "zzzzqqqq")
    rows = recent_queries(tmp_path / "idx" / "sift.db")
    assert [(r.query, r.total) for r in rows] == [
        ("zzzzqqqq", 0),
        ("chain tool", 1),
    ]
    assert all(r.took_ms >= 0 for r in rows)
    assert all(r.at.utcoffset() == timedelta(0) for r in rows)


def test_syntax_error_is_not_logged(mini_cli, tmp_path: Path) -> None:
    assert code_of("search", '"unclosed') == 3
    assert recent_queries(tmp_path / "idx" / "sift.db") == []


def test_stats_without_queries(mini_cli) -> None:
    assert "no queries logged" in ok("stats").stdout


def test_stats_lists_the_last_ten_queries_newest_first(mini_cli) -> None:
    for number in range(12):
        ok("search", f"word{number}")
    out = ok("stats").stdout
    assert "last 10 queries:" in out
    listed = [line for line in out.splitlines() if " UTC " in line]
    assert [line.split()[-1] for line in listed] == [
        f"word{n}" for n in range(11, 1, -1)
    ]
    assert "     0 hits" in listed[0]


def test_search_dash_reads_stdin(mini_cli) -> None:
    out = ok("search", "-", input="chain\n").stdout
    assert "bicycle-repair.md" in out


def test_zero_hits_is_not_an_error(mini_cli) -> None:
    assert "0 hits" in ok("search", "zzzzqqqq").stdout


def test_stats(mini_cli) -> None:
    out = ok("stats").stdout
    assert "documents: 8" in out
    assert "vocabulary: " in out


def test_index_full_then_incremental(
    mini_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    args = ["index", "--corpus", str(mini_root)]
    out = ok(*args).stdout
    assert "documents: 8" in out
    assert "full rebuild: parsed 8, unchanged 0, removed 0" in out
    assert (tmp_path / ".sift" / "segment.sft").is_file()
    assert (tmp_path / ".sift" / "sift.db").is_file()
    assert (tmp_path / ".sift" / "manifest.json").is_file()
    out = ok(*args).stdout
    assert "incremental: parsed 0, unchanged 8, removed 0" in out
    assert "full rebuild: parsed 8" in ok(*args, "--full").stdout


def test_sift_index_env_selects_the_directory(
    mini_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "elsewhere"
    monkeypatch.setenv("SIFT_INDEX", str(target))
    ok("index", "--corpus", str(mini_root))
    assert (target / "segment.sft").is_file()
    assert not (tmp_path / ".sift").exists()
    ok("search", "chain")


def test_search_reads_the_segment_not_the_corpus(
    mini_cli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        Document,
        "from_markdown",
        lambda *a, **k: pytest.fail("a post was parsed"),
    )
    (tmp_path / "sift.toml").unlink()
    monkeypatch.setenv("SIFT_INDEX", str(tmp_path / "idx"))
    assert "bicycle-repair.md" in ok("search", "chain").stdout


def test_search_uses_the_limit_of_the_config(mini_cli, tmp_path: Path) -> None:
    config = tmp_path / "sift.toml"
    config.write_text(config.read_text() + "[search]\nlimit = 1\n")
    assert ok("search", "tea", "OR", "bicycle").stdout.count(".md") == 1


def test_bad_config_exits_1(mini_cli, tmp_path: Path) -> None:
    (tmp_path / "sift.toml").write_text("[search]\nlimit = 0\n")
    result = invoke("search", "chain")
    assert result.exit_code == 1
    assert result.stderr.startswith("error: sift.toml: [search] limit")


def test_corrupt_segment_exits_1(mini_cli, tmp_path: Path) -> None:
    segment = tmp_path / "idx" / "segment.sft"
    segment.write_bytes(b"NOPE" + segment.read_bytes()[4:])
    result = invoke("search", "chain")
    assert result.exit_code == 1
    assert "bad magic" in result.stderr


def test_stats_prints_counts_and_top_terms(mini_cli) -> None:
    out = ok("stats").stdout
    assert "segment: " in out
    assert out.count("\n") == 3 + 20 + 1  # + "no queries logged"


def test_show_prints_the_document(mini_cli) -> None:
    out = ok("show", "0").stdout
    assert out.startswith("title: ")
    assert "\npath: " in out


def test_show_unknown_id_exits_1(mini_cli) -> None:
    result = invoke("show", "99")
    assert result.exit_code == 1
    assert result.stderr == "error: no document with id 99\n"


def test_open_runs_the_editor_on_the_file(
    mini_cli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "args.txt"
    script = tmp_path / "editor.sh"
    script.write_text(f'#!/bin/sh\necho "$@" > {log}\n')
    script.chmod(0o755)
    monkeypatch.setenv("EDITOR", str(script))
    ok("open", "0")
    assert log.read_text().strip().endswith(".md")


def test_open_missing_editor_exits_1(
    mini_cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EDITOR", "/nonexistent/editor")
    result = invoke("open", "0")
    assert result.exit_code == 1
    assert "cannot run editor" in result.stderr


def test_bench_search_runs_every_query(
    mini_cli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    queries = tmp_path / "queries.txt"
    queries.write_text("chain\n\n编译\n", encoding="utf-8")
    monkeypatch.setattr(cli, "QUERIES", queries)
    assert "total for 2 queries" in ok("bench", "search").stdout


def test_bench_search_profile_writes_pstats(
    mini_cli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    queries = tmp_path / "queries.txt"
    queries.write_text("chain\n", encoding="utf-8")
    target = tmp_path / "out" / "profile.pstats"
    monkeypatch.setattr(cli, "QUERIES", queries)
    monkeypatch.setattr(cli, "PROFILE", target)
    result = ok("bench", "search", "--profile")
    assert f"profile written to {target}" in result.stdout
    profile = pstats.Stats(str(target)).get_stats_profile()
    assert "search" in profile.func_profiles


def test_bench_search_without_profile_writes_nothing(
    mini_cli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    queries = tmp_path / "queries.txt"
    queries.write_text("chain\n", encoding="utf-8")
    target = tmp_path / "out" / "profile.pstats"
    monkeypatch.setattr(cli, "QUERIES", queries)
    monkeypatch.setattr(cli, "PROFILE", target)
    ok("bench", "search")
    assert not target.parent.exists()


def test_bench_search_logs_its_queries(
    mini_cli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    queries = tmp_path / "queries.txt"
    queries.write_text("chain\n编译\n", encoding="utf-8")
    monkeypatch.setattr(cli, "QUERIES", queries)
    ok("bench", "search")
    ok("bench", "search")
    rows = recent_queries(tmp_path / "idx" / "sift.db", 10)
    assert sorted(row.query for row in rows) == ["chain"] * 2 + ["编译"] * 2


def test_similar_lists_k_posts_best_first(mini_cli) -> None:
    lines = ok("similar", "0", "-k", "3").stdout.splitlines()
    assert len(lines) == 3
    scores = [float(line.split()[0]) for line in lines]
    assert scores[0] == 1.0
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= score <= 1.0 for score in scores)
    assert lines[0].split()[1] == "0"


def test_similar_defaults_to_five_posts(mini_cli) -> None:
    assert len(ok("similar", "0").stdout.splitlines()) == 5


def test_similar_unknown_doc_exits_1(mini_cli) -> None:
    result = invoke("similar", "99")
    assert result.exit_code == 1
    assert "no document with id 99" in result.stderr


def test_similar_k_below_one_is_a_usage_error(mini_cli) -> None:
    assert code_of("similar", "0", "-k", "0") == 2


def test_similar_without_index_exits_4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SIFT_INDEX", str(tmp_path / "none"))
    assert code_of("similar", "0") == 4


def test_report_writes_figures_and_table(mini_cli, tmp_path: Path) -> None:
    out = tmp_path / "rep"
    lines = ok("report", "--out", str(out)).stdout.splitlines()
    names = sorted(Path(line).name for line in lines)
    assert names == [
        "heaps.png",
        "latency-hist.png",
        "posts-per-month.png",
        "report.md",
        "zipf.png",
    ]
    for name in names:
        assert (out / name).stat().st_size > 0
    assert (out / "zipf.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert "| documents | 8 |" in (out / "report.md").read_text("utf-8")


def test_bench_index_prints_a_table(mini_cli) -> None:
    out = ok(
        "bench",
        "index",
        "--repeat",
        "2",
        "--jobs",
        "1,2",
        "--mode",
        "thread,process",
        "--rounds",
        "1",
    ).stdout
    lines = out.splitlines()
    assert lines[0].startswith("corpus: 8 files x 2 = 16 documents")
    assert "GIL" in lines[1]
    assert lines[2].split() == ["jobs", "thread", "process"]
    row1, row2 = (line.split() for line in lines[3:])
    assert row1[0] == "1" and row1[2:4] == ["s", "1.00x"]
    assert row1[1] == row1[4] and row1[5:] == ["s", "1.00x"]
    assert row2[0] == "2" and row2[3].endswith("x")


@pytest.mark.parametrize("mode", ["process", "thread", "interp"])
def test_index_jobs_gives_the_same_segment(
    mini_cli, tmp_path: Path, mode: str
) -> None:
    serial = (tmp_path / "idx" / "segment.sft").read_bytes()
    ok("index", "--full", "--jobs", "3", "--mode", mode)
    assert (tmp_path / "idx" / "segment.sft").read_bytes() == serial


@pytest.mark.parametrize(
    "args",
    [
        ["index", "--jobs", "0"],
        ["index", "--jobs", "x"],
        ["index", "--mode", "fork"],
        ["bench", "index", "--jobs", "1,0"],
        ["bench", "index", "--jobs", ""],
        ["bench", "index", "--mode", "thread,fork"],
        ["bench", "index", "--repeat", "0"],
        ["bench", "index", "--rounds", "0"],
    ],
)
def test_bad_parallel_options_exit_2(args: list[str]) -> None:
    assert code_of(*args) == 2


def test_bad_mode_names_the_option_and_the_choices() -> None:
    result = invoke("index", "--mode", "fork")
    assert "Invalid value for '--mode'" in result.stderr
    assert "use one of process, thread, interp" in result.stderr


def test_index_with_bad_front_matter_exits_1_in_every_mode(
    mini_cli, tmp_path: Path, mini_root: Path
) -> None:
    corpus = tmp_path / "posts"
    shutil.copytree(mini_root, corpus)
    for name in ("x1.md", "x2.md"):
        (corpus / name).write_text("---\ntitle: [oops\n---\n")
    for mode in ("process", "thread", "interp"):
        result = invoke(
            "index", "--corpus", str(corpus), "--jobs", "3", "--mode", mode
        )
        assert result.exit_code == 1
        assert result.stderr.startswith("error: 2 files failed")
        assert "x1.md" in result.stderr and "x2.md" in result.stderr


def test_bench_index_without_corpus_exits_1(mini_cli, tmp_path: Path) -> None:
    (tmp_path / "sift.toml").write_text(
        f'[index]\ncorpus = "{tmp_path / "none"}"\n', encoding="utf-8"
    )
    assert code_of("bench", "index", "--rounds", "1") == 1


def test_version_and_bench_do_not_import_sqlalchemy() -> None:
    code = (
        "import sys, sift.cli, typer.main;"
        "typer.main.get_command(sift.cli.app);"
        "assert 'sqlalchemy' not in sys.modules, 'imported'"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert done.returncode == 0, done.stderr


def test_help_and_bench_start_without_heavy_imports() -> None:
    code = (
        "import sys, sift.cli;"
        "sift.cli.main(['--version']);"
        "sift.cli.main(['similar', '--help']);"
        "sift.cli.main(['report', '--help']);"
        "sift.cli.main(['bench', 'index', '--help']);"
        "heavy = {'sqlalchemy', 'asyncio', 'numpy', 'pandas', 'matplotlib'}"
        " & set(sys.modules);"
        "assert not heavy, heavy"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["search"],
        ["nope"],
        ["bench"],
        ["show", "x"],
        ["show", "-1"],
        ["search", "--limit", "0", "a"],
        ["search", "--limit", "101", "a"],
        ["search", "--limit", "x", "a"],
        ["serve", "--port", "x"],
        ["serve", "--port", "-1"],
        ["serve", "--port", "65536"],
        ["serve", "--max-pending", "0"],
        ["serve", "--raw", "--port", "x"],
        ["serve", "--raw", "--max-pending", "0"],
        ["stats", "extra"],
        ["--nope"],
    ],
)
def test_bad_usage_exits_2(args: list[str]) -> None:
    assert code_of(*args) == 2


def test_version() -> None:
    result = invoke("--version")
    assert result.exit_code == 0
    assert result.stdout == f"sift {sift.__version__}\n"


COMMANDS = [
    [],
    ["index"],
    ["search"],
    ["show"],
    ["stats"],
    ["open"],
    ["serve"],
    ["gui"],
    ["bench"],
    ["bench", "index"],
    ["bench", "search"],
]


@pytest.mark.parametrize("path", COMMANDS, ids=" ".join)
@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_exits_0_for_every_command(path: list[str], flag: str) -> None:
    result = invoke(*path, flag)
    assert result.exit_code == 0
    assert result.stdout.lstrip().startswith("Usage: sift")
    assert result.stderr == ""


def test_help_lists_the_commands_and_the_exit_codes() -> None:
    out = invoke("--help").stdout
    for name in ("index", "search", "show", "stats", "open", "serve", "gui"):
        assert name in out
    assert "bench" in out
    assert "--version" in out and "--debug" in out
    assert "Exit codes: 0 ok, 2 usage, 3 bad query, 4 no index" in out


def test_help_has_no_escape_codes_and_keeps_square_brackets() -> None:
    out = invoke("search", "--help").stdout
    assert "\x1b" not in out
    assert "--limit" in out and "--json" in out and "--no-log" in out


BOX = set("╭╮╰╯│─┃━┏┓┗┛┌┐└┘├┤┬┴┼")


def test_help_and_usage_errors_are_plain_in_a_pipe() -> None:
    help_out = invoke("--help").stdout
    assert not BOX & set(help_out)
    assert "Usage: sift [OPTIONS] COMMAND [ARGS]..." in help_out
    assert "Exit codes: 0 ok, 2 usage" in help_out
    result = invoke("search", "--limit", "101", "a")
    assert result.exit_code == 2
    assert not BOX & set(result.stderr + result.stdout)
    assert "Error: Invalid value for '--limit'" in result.stderr
    assert "Usage: sift search" in result.stderr


@pytest.mark.parametrize("path", COMMANDS, ids=" ".join)
def test_help_has_no_box_in_a_pipe(path: list[str]) -> None:
    assert not BOX & set(invoke(*path, "--help").stdout)


def test_no_color_and_dumb_terminals_get_plain_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in (("NO_COLOR", "1"), ("TERM", "dumb")):
        monkeypatch.setenv(name, value)
        assert cli.markup_mode() is None
        monkeypatch.delenv(name)
        monkeypatch.setenv("TERM", "xterm")


def test_a_terminal_gets_rich_help_and_usage_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sift import render

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(render, "wants_rich", lambda stream: True)
    assert cli.markup_mode() == "rich"
    monkeypatch.setattr(cli.app, "rich_markup_mode", cli.markup_mode())
    monkeypatch.setattr(cli.bench_app, "rich_markup_mode", cli.markup_mode())
    assert BOX & set(invoke("--help").stdout)
    result = invoke("search", "--limit", "101", "a")
    assert result.exit_code == 2
    assert BOX & set(result.stderr)


def test_one_terminal_stream_is_not_enough_for_rich_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sift import render

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.setattr(render, "wants_rich", lambda s: s is sys.stdout)
    assert cli.markup_mode() is None


def test_serve_help_shows_the_same_default_as_the_raw_server() -> None:
    from sift.server.raw import MAX_PENDING

    command = typer.main.get_command(cli.app)
    assert hasattr(command, "commands")
    serve = command.commands["serve"]
    defaults = {p.name: p.default for p in serve.params}
    assert defaults["max_pending"] == MAX_PENDING
    assert defaults["port"] == 8000
    assert defaults["host"] == "127.0.0.1"


def test_no_command_prints_the_help_and_exits_2() -> None:
    result = invoke()
    assert result.exit_code == 2
    assert "Commands" in result.output


def test_usage_error_goes_to_stderr_and_names_the_option() -> None:
    result = invoke("serve", "--port", "65536")
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Invalid value for '--port'" in result.stderr
    assert "port out of range" in result.stderr


def test_query_syntax_error_exits_3_with_a_caret(mini_cli) -> None:
    result = invoke("search", "a AND")
    assert result.exit_code == 3
    assert result.stderr == "expected a term\n  a AND\n       ^\n"
    assert result.stdout == ""


@pytest.mark.parametrize("command", ["stats", "show 0", "open 0"])
def test_missing_index_dir_exits_4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, command: str
) -> None:
    missing = tmp_path / "nope"
    monkeypatch.setenv("SIFT_INDEX", str(missing))
    result = invoke(*command.split())
    assert result.exit_code == 4
    assert (
        result.stderr
        == f"sift: no index at {missing}, run 'sift index' first\n"
    )


def test_search_with_missing_index_dir_exits_4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SIFT_INDEX", str(tmp_path / "nope"))
    assert code_of("search", "rust") == 4


def test_index_dir_without_a_segment_exits_4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SIFT_INDEX", str(tmp_path))
    assert code_of("search", "chain") == 4


def test_default_index_dir_is_dot_sift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    result = invoke("search", "chain")
    assert result.exit_code == 4
    assert result.stderr == "sift: no index at .sift, run 'sift index' first\n"


def raising(error: BaseException):
    """Return a load_config that raises error."""

    def boom() -> None:
        raise error

    return boom


def test_sift_error_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sift.config.load_config", raising(ConfigError("bad setting"))
    )
    result = invoke("stats")
    assert result.exit_code == 1
    assert result.stderr == "error: bad setting\n"


def test_group_of_sift_errors_exits_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = ExceptionGroup(
        "2 files failed", [ConfigError("a"), ConfigError("b")]
    )
    monkeypatch.setattr("sift.config.load_config", raising(group))
    result = invoke("stats")
    assert result.exit_code == 1
    assert result.stderr == "error: 2 files failed\n  a\n  b\n"


def test_group_with_a_bug_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = ExceptionGroup("mixed", [ConfigError("a"), KeyError("b")])
    monkeypatch.setattr("sift.config.load_config", raising(group))
    result = invoke("stats")
    assert result.exit_code == 1
    assert isinstance(result.exception, ExceptionGroup)
    assert result.exception.message == "mixed"


def test_bug_is_not_turned_into_an_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sift.config.load_config", raising(KeyError("b")))
    result = invoke("stats")
    assert isinstance(result.exception, KeyError)


def test_python_dash_m_sift_is_the_same_cli() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "sift", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout == f"sift {sift.__version__}\n"


def test_main_returns_on_success_and_exits_on_failure(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["stats"]) is None
    assert "documents: 8" in capsys.readouterr().out
    assert cli.main(["--version"]) is None
    with pytest.raises(SystemExit) as caught:
        cli.main(["search", "a AND"])
    assert caught.value.code == 3
    with pytest.raises(SystemExit) as caught:
        cli.main(["search"])
    assert caught.value.code == 2


def test_keyboard_interrupt_exits_130_quietly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sift.config.load_config", raising(KeyboardInterrupt())
    )
    result = invoke("stats")
    assert result.exit_code == 130
    assert result.stderr == "interrupted\n"
    assert "Traceback" not in result.stderr


def test_index_with_missing_corpus_exits_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    missing = tmp_path / "posts"
    result = invoke("index", "--corpus", str(missing))
    assert result.exit_code == 1
    assert result.stderr == f"error: no corpus at {missing}\n"
    assert not (tmp_path / ".sift" / "segment.sft").exists()


def test_bench_index_with_missing_corpus_exits_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    result = invoke("bench", "index")
    assert result.exit_code == 1
    assert "error: no corpus at corpus/posts" in result.stderr


def test_unwritable_log_does_not_fail_the_search(
    mini_cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: object) -> None:
        raise SiftError("cannot log the query: secret-query-text")

    monkeypatch.setattr("sift.storage.db.log_query", broken)
    result = ok("search", "chain")
    assert "1 hits" in result.stdout
    assert result.stderr.count("\n") == 1
    assert "warning: query not logged" in result.stderr
    assert "secret" not in result.stderr


def test_read_only_database_does_not_fail_the_search(
    mini_cli, tmp_path: Path
) -> None:
    db = tmp_path / "idx" / "sift.db"
    db.chmod(0o444)
    try:
        result = ok("search", "chain")
    finally:
        db.chmod(0o644)
    assert "1 hits" in result.stdout
    assert "query not logged" in result.stderr


def test_show_reads_one_document(
    mini_cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("show must not load every document")

    monkeypatch.setattr("sift.storage.db.load_documents", forbidden)
    assert "title: " in ok("show", "0").stdout


def test_limit_above_the_maximum_is_a_usage_error() -> None:
    result = invoke("search", "--limit", "101", "a")
    assert result.exit_code == 2
    assert "between 1 and 100" in result.stderr


# --- rich, --debug and the plain fallback -----------------------------


def test_plain_output_in_a_pipe_has_no_escape_codes(mini_cli) -> None:
    result = ok("search", "chain")
    assert "\x1b" not in result.stdout + result.stderr
    assert result.stdout.startswith(" 1  ")


def test_no_color_keeps_the_plain_output(
    mini_cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    assert ok("search", "chain").stdout.startswith(" 1  ")


def test_a_terminal_gets_the_rich_table(
    mini_cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sift import render

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.setattr(render, "wants_rich", lambda stream: True)
    out = ok("search", "chain").stdout
    assert "╭" in out and "bicycle-repair.md" in out
    assert "1 hits in 8 files: index opened in" in out


def test_json_stays_plain_on_a_terminal(
    mini_cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sift import render

    monkeypatch.setattr(render, "wants_rich", lambda stream: True)
    out = ok("search", "--json", "chain").stdout
    assert "\x1b" not in out
    assert json.loads(out)["total"] == 1


def test_index_draws_a_progress_bar_only_on_a_terminal(
    mini_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from sift import render

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(render, "wants_rich", lambda stream: True)
    result = ok("index", "--corpus", str(mini_root))
    assert "documents: 8" in result.stdout
    assert "full rebuild: parsed 8" in result.stdout


def test_debug_prints_a_traceback_and_keeps_the_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sift.config.load_config", raising(ConfigError("bad setting"))
    )
    plain = invoke("stats")
    assert "Traceback" not in plain.stderr
    result = invoke("--debug", "stats")
    assert result.exit_code == 1
    assert "Traceback" in result.stderr
    assert result.stderr.rstrip().endswith("error: bad setting")


def test_debug_sets_the_log_level_and_the_traceback_hook(
    mini_cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    ok("--debug", "stats")
    assert logging.getLogger("sift").level == logging.DEBUG
    assert sys.excepthook is not sys.__excepthook__
    ok("stats")
    assert logging.getLogger("sift").level == logging.WARNING


# FastAPI on uvicorn is the default; --raw is the server of chapter 17
SERVERS = pytest.mark.parametrize(
    "flags", [[], ["--raw"]], ids=["fastapi", "raw"]
)


@SERVERS
def test_serve_without_an_index_exits_4(
    flags: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    result = invoke("serve", *flags, "--port", "0")
    assert result.exit_code == 4
    assert "run 'sift index' first" in result.stderr


@SERVERS
def test_serve_on_a_corrupt_index_says_so_once_and_exits_1(
    flags: list[str], mini_cli, tmp_path: Path
) -> None:
    segment = tmp_path / "idx" / "segment.sft"
    segment.write_bytes(b"NOPE" + segment.read_bytes()[4:])
    result = invoke("serve", *flags, "--port", "0")
    assert result.exit_code == 1
    err = result.stderr
    assert err.startswith("error: ")
    assert "bad magic" in err
    assert err.count("\n") == 1  # no traceback from uvicorn


@SERVERS
def test_serve_on_a_busy_port_exits_1(flags: list[str], mini_cli) -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        result = invoke("serve", *flags, "--port", str(port))
    assert result.exit_code == 1
    assert result.stderr == (
        f"error: cannot listen on 127.0.0.1:{port}: address already in use\n"
    )


def start_server(tmp_path: Path, *flags: str) -> subprocess.Popen[str]:
    """Start ``python -m sift serve`` on a free port in tmp_path."""
    env = {k: v for k, v in os.environ.items() if k != "SIFT_INDEX"}
    return subprocess.Popen(
        [sys.executable, "-m", "sift", "serve", "--port", "0", *flags],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


@SERVERS
def test_serve_answers_and_stops_on_sigterm(
    flags: list[str], mini_cli, tmp_path: Path
) -> None:
    server = start_server(tmp_path, *flags)
    try:
        assert server.stdout is not None
        banner = server.stdout.readline().strip()
        assert banner.startswith("listening on http://127.0.0.1:")
        url = banner.removeprefix("listening on ")
        with urllib.request.urlopen(f"{url}/search?q=chain") as response:
            body = json.load(response)
        assert body["total"] == 1
        server.send_signal(signal.SIGTERM)
        assert server.wait(timeout=10) == 0
        assert server.stderr is not None
        log = server.stderr.read()
    finally:
        if server.poll() is None:
            server.kill()
        server.communicate()
    assert "GET /search?q=chain" in log
    assert " 200" in log


@SERVERS
def test_serve_quiet_logs_no_requests(
    flags: list[str], mini_cli, tmp_path: Path
) -> None:
    server = start_server(tmp_path, "--quiet", *flags)
    try:
        assert server.stdout is not None
        url = server.stdout.readline().strip().removeprefix("listening on ")
        with urllib.request.urlopen(f"{url}/health") as response:
            assert response.status == 200
        server.send_signal(signal.SIGTERM)
        assert server.wait(timeout=10) == 0
        assert server.stderr is not None
        assert server.stderr.read() == ""
    finally:
        if server.poll() is None:
            server.kill()
        server.communicate()


@SERVERS
def test_serve_is_asked_with_the_clients(
    flags: list[str], mini_cli, tmp_path: Path
) -> None:
    from sift.client import AsyncSiftClient, SiftClient

    server = start_server(tmp_path, "--quiet", *flags)
    try:
        assert server.stdout is not None
        url = server.stdout.readline().strip().removeprefix("listening on ")
        with SiftClient(url) as client:
            assert client.health().docs == 8
            hit = client.search("chain", limit=1).hits[0]
            assert client.document(hit.doc_id).title == hit.title

        async def ask() -> int:
            async with AsyncSiftClient(url) as client:
                return (await client.health()).docs

        assert asyncio.run(ask()) == 8
        server.send_signal(signal.SIGTERM)
        assert server.wait(timeout=10) == 0
    finally:
        if server.poll() is None:
            server.kill()
        server.communicate()


def test_serve_without_the_web_extra_says_so(
    mini_cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "sift.server.app", None)
    result = invoke("serve", "--port", "0")
    assert result.exit_code == 1
    err = result.stderr
    assert err.startswith("error: sift serve needs the web extra")
    assert "--raw" in err


# sift gui: the window itself is tested in tests/tk_display


def test_gui_without_an_index_exits_4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    for flags in ([], ["--tk"]):
        result = invoke("gui", *flags)
        assert result.exit_code == 4
        assert "run 'sift index' first" in result.stderr


def test_gui_without_a_display_exits_1(
    monkeypatch: pytest.MonkeyPatch, mini_cli
) -> None:
    pytest.importorskip("tkinter")
    pytest.importorskip("sv_ttk")
    pytest.importorskip("darkdetect")
    monkeypatch.delenv("DISPLAY", raising=False)
    result = invoke("gui", "--tk")
    assert result.exit_code == 1
    assert result.stderr.startswith("error: cannot open a display")


@pytest.mark.parametrize("missing", ["sv_ttk", "darkdetect"])
def test_gui_without_the_extra_exits_1(
    missing: str, monkeypatch: pytest.MonkeyPatch, mini_cli
) -> None:
    monkeypatch.delitem(sys.modules, "sift.gui.tk_app", raising=False)
    monkeypatch.setitem(sys.modules, missing, None)
    result = invoke("gui", "--tk")
    assert result.exit_code == 1
    assert f"the gui extra ({missing} is missing)" in result.stderr
    assert "pip install 'sift[gui]'" in result.stderr


def test_gui_without_pyside6_exits_1(
    monkeypatch: pytest.MonkeyPatch, mini_cli
) -> None:
    monkeypatch.delitem(sys.modules, "sift.gui.qt.app", raising=False)
    monkeypatch.setitem(sys.modules, "PySide6", None)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", None)
    result = invoke("gui")
    assert result.exit_code == 1
    assert "the gui extra (PySide6" in result.stderr
    assert "pip install 'sift[gui]'" in result.stderr


def test_gui_qt_without_a_display_exits_1(
    monkeypatch: pytest.MonkeyPatch, mini_cli
) -> None:
    pytest.importorskip("PySide6")
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM"):
        monkeypatch.delenv(name, raising=False)
    result = invoke("gui")
    assert result.exit_code == 1
    assert result.stderr.startswith("error: cannot open a display")


def test_gui_without_tkinter_exits_1(
    monkeypatch: pytest.MonkeyPatch, mini_cli
) -> None:
    monkeypatch.delitem(sys.modules, "sift.gui.tk_app", raising=False)
    monkeypatch.setitem(sys.modules, "tkinter", None)
    result = invoke("gui", "--tk")
    assert result.exit_code == 1
    assert "needs tkinter" in result.stderr


def test_version_does_not_import_the_gui() -> None:
    code = (
        "import sys, sift.cli as c; c.main(['--version']); "
        "bad = [m for m in ('tkinter', 'sv_ttk', 'darkdetect', "
        "'PySide6', 'qtawesome') "
        "if m in sys.modules]; assert not bad, bad"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr

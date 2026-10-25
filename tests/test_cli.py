"""Tests for the command line in sift.cli."""

import asyncio
import io
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import urllib.request
from datetime import timedelta
from pathlib import Path
from types import ModuleType

import pytest

import sift
import sift.cli as cli
from sift.document import Document
from sift.errors import ConfigError, SiftError
from sift.storage.db import recent_queries


@pytest.fixture(autouse=True)
def no_sift_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test with SIFT_INDEX unset."""
    monkeypatch.delenv("SIFT_INDEX", raising=False)


@pytest.fixture
def mini_cli(
    monkeypatch: pytest.MonkeyPatch, mini_root: Path, tmp_path: Path
) -> ModuleType:
    """Work in a temp dir with a sift.toml and an index of the mini posts."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sift.toml").write_text(
        f'[index]\ncorpus = "{mini_root}"\npath = "{tmp_path / "idx"}"\n',
        encoding="utf-8",
    )
    cli.main(["index"])
    return cli


def run_main(*args: str) -> int:
    """Run main() with the args; return the exit status."""
    with pytest.raises(SystemExit) as caught:
        cli.main(args)
    assert isinstance(caught.value.code, int)
    return caught.value.code


def test_search_prints_ranked_hits(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.main(["search", "chain", "tool"])
    out = capsys.readouterr().out
    assert "bicycle-repair.md" in out
    assert "Fixing a bicycle chain" in out
    assert "[chain]" in out.lower()
    assert "1 hits in 8 files: index opened in" in out


def test_search_words_are_joined_into_one_query(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.main(["search", '"chain', 'tool"'])
    assert "1 hits" in capsys.readouterr().out


def test_search_limit(mini_cli, capsys: pytest.CaptureFixture[str]) -> None:
    mini_cli.main(["search", "--limit", "1", "tea", "OR", "bicycle"])
    out = capsys.readouterr().out
    assert out.count(".md") == 1


def test_search_limit_accepts_the_maximum(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.main(["search", "--limit", "100", "tea", "OR", "bicycle"])
    assert capsys.readouterr().out.count(".md") >= 1


def test_search_json(mini_cli, capsys: pytest.CaptureFixture[str]) -> None:
    mini_cli.main(["search", "--json", "chain", "tool"])
    data = json.loads(capsys.readouterr().out)
    assert data["total"] == 1
    assert data["hits"][0]["path"].endswith("bicycle-repair.md")
    assert data["hits"][0]["title"] == "Fixing a bicycle chain"


def test_search_no_log_does_not_log(
    mini_cli, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    mini_cli.main(["search", "--no-log", "chain"])
    assert "hits in 8 files" in capsys.readouterr().out
    assert recent_queries(tmp_path / "idx" / "sift.db") == []


def test_search_logs_the_query(
    mini_cli, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    mini_cli.main(["search", "chain", "tool"])
    capsys.readouterr()
    mini_cli.main(["search", "--json", "zzzzqqqq"])
    capsys.readouterr()
    rows = recent_queries(tmp_path / "idx" / "sift.db")
    assert [(r.query, r.total) for r in rows] == [
        ("zzzzqqqq", 0),
        ("chain tool", 1),
    ]
    assert all(r.took_ms >= 0 for r in rows)
    assert all(r.at.utcoffset() == timedelta(0) for r in rows)


def test_syntax_error_is_not_logged(mini_cli, tmp_path: Path) -> None:
    assert run_main("search", '"unclosed') == 3
    assert recent_queries(tmp_path / "idx" / "sift.db") == []


def test_stats_without_queries(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.main(["stats"])
    assert "no queries logged" in capsys.readouterr().out


def test_stats_lists_the_last_ten_queries_newest_first(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    for number in range(12):
        mini_cli.main(["search", f"word{number}"])
    capsys.readouterr()
    mini_cli.main(["stats"])
    out = capsys.readouterr().out
    assert "last 10 queries:" in out
    listed = [line for line in out.splitlines() if " UTC " in line]
    assert [line.split()[-1] for line in listed] == [
        f"word{n}" for n in range(11, 1, -1)
    ]
    assert "     0 hits" in listed[0]


def test_search_dash_reads_stdin(
    mini_cli,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("chain\n"))
    mini_cli.main(["search", "-"])
    assert "bicycle-repair.md" in capsys.readouterr().out


def test_zero_hits_is_not_an_error(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.main(["search", "zzzzqqqq"])
    assert "0 hits" in capsys.readouterr().out


def test_stats(mini_cli, capsys: pytest.CaptureFixture[str]) -> None:
    mini_cli.main(["stats"])
    out = capsys.readouterr().out
    assert "documents: 8" in out
    assert "vocabulary: " in out


def test_index_full_then_incremental(
    mini_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    args = ["index", "--corpus", str(mini_root)]
    cli.main(args)
    out = capsys.readouterr().out
    assert "documents: 8" in out
    assert "full rebuild: parsed 8, unchanged 0, removed 0" in out
    assert (tmp_path / ".sift" / "segment.sft").is_file()
    assert (tmp_path / ".sift" / "sift.db").is_file()
    assert (tmp_path / ".sift" / "manifest.json").is_file()
    cli.main(args)
    out = capsys.readouterr().out
    assert "incremental: parsed 0, unchanged 8, removed 0" in out
    cli.main([*args, "--full"])
    assert "full rebuild: parsed 8" in capsys.readouterr().out


def test_sift_index_env_selects_the_directory(
    mini_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "elsewhere"
    monkeypatch.setenv("SIFT_INDEX", str(target))
    cli.main(["index", "--corpus", str(mini_root)])
    assert (target / "segment.sft").is_file()
    assert not (tmp_path / ".sift").exists()
    cli.main(["search", "chain"])


def test_search_reads_the_segment_not_the_corpus(
    mini_cli,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        Document,
        "from_markdown",
        lambda *a, **k: pytest.fail("a post was parsed"),
    )
    (tmp_path / "sift.toml").unlink()
    monkeypatch.setenv("SIFT_INDEX", str(tmp_path / "idx"))
    mini_cli.main(["search", "chain"])
    assert "bicycle-repair.md" in capsys.readouterr().out


def test_search_uses_the_limit_of_the_config(
    mini_cli, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "sift.toml"
    config.write_text(config.read_text() + "[search]\nlimit = 1\n")
    mini_cli.main(["search", "tea", "OR", "bicycle"])
    assert capsys.readouterr().out.count(".md") == 1


def test_bad_config_exits_1(
    mini_cli, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "sift.toml").write_text("[search]\nlimit = 0\n")
    assert run_main("search", "chain") == 1
    assert capsys.readouterr().err.startswith(
        "error: sift.toml: [search] limit"
    )


def test_corrupt_segment_exits_1(
    mini_cli, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    segment = tmp_path / "idx" / "segment.sft"
    segment.write_bytes(b"NOPE" + segment.read_bytes()[4:])
    assert run_main("search", "chain") == 1
    assert "bad magic" in capsys.readouterr().err


def test_stats_prints_counts_and_top_terms(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.main(["stats"])
    out = capsys.readouterr().out
    assert "segment: " in out
    assert out.count("\n") == 3 + 20 + 1  # + "no queries logged"


def test_show_prints_the_document(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.main(["show", "0"])
    out = capsys.readouterr().out
    assert out.startswith("title: ")
    assert "\npath: " in out


def test_show_unknown_id_exits_1(
    mini_cli,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_main("show", "99") == 1
    assert capsys.readouterr().err == "error: no document with id 99\n"


def test_open_runs_the_editor_on_the_file(
    mini_cli,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    log = tmp_path / "args.txt"
    script = tmp_path / "editor.sh"
    script.write_text(f'#!/bin/sh\necho "$@" > {log}\n')
    script.chmod(0o755)
    monkeypatch.setenv("EDITOR", str(script))
    mini_cli.main(["open", "0"])
    assert log.read_text().strip().endswith(".md")


def test_open_missing_editor_exits_1(
    mini_cli,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("EDITOR", "/nonexistent/editor")
    assert run_main("open", "0") == 1
    assert "cannot run editor" in capsys.readouterr().err


def test_bench_search_runs_every_query(
    mini_cli,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    queries = tmp_path / "queries.txt"
    queries.write_text("chain\n\n编译\n", encoding="utf-8")
    monkeypatch.setattr(mini_cli, "QUERIES", queries)
    mini_cli.main(["bench", "search"])
    out = capsys.readouterr().out
    assert "total for 2 queries" in out


def test_bench_index_prints_a_table(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.main(
        [
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
        ]
    )
    lines = capsys.readouterr().out.splitlines()
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
    mini_cli.main(["index", "--full", "--jobs", "3", "--mode", mode])
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
    assert run_main(*args) == 2


def test_index_with_bad_front_matter_exits_1_in_every_mode(
    mini_cli,
    tmp_path: Path,
    mini_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus = tmp_path / "posts"
    shutil.copytree(mini_root, corpus)
    for name in ("x1.md", "x2.md"):
        (corpus / name).write_text("---\ntitle: [oops\n---\n")
    for mode in ("process", "thread", "interp"):
        code = run_main(
            "index", "--corpus", str(corpus), "--jobs", "3", "--mode", mode
        )
        assert code == 1
        err = capsys.readouterr().err
        assert err.startswith("error: 2 files failed")
        assert "x1.md" in err and "x2.md" in err


def test_bench_index_without_corpus_exits_1(
    mini_cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sift.toml").write_text(
        f'[index]\ncorpus = "{tmp_path / "none"}"\n', encoding="utf-8"
    )
    assert run_main("bench", "index", "--rounds", "1") == 1


def test_version_and_bench_do_not_import_sqlalchemy() -> None:
    code = (
        "import sys, sift.cli;"
        "assert 'sqlalchemy' not in sys.modules, 'imported';"
        "sift.cli.build_parser()"
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
        ["search", "--limit", "0", "a"],
        ["search", "--limit", "101", "a"],
        ["search", "--limit", "x", "a"],
        ["serve", "--port", "x"],
        ["serve", "--port", "-1"],
        ["serve", "--port", "65536"],
        ["serve", "--max-pending", "0"],
        ["serve", "--raw", "--port", "x"],
        ["serve", "--raw", "--max-pending", "0"],
    ],
)
def test_bad_usage_exits_2(args: list[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        cli.main(args)
    assert caught.value.code == 2


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        cli.main(["--version"])
    assert caught.value.code == 0
    assert capsys.readouterr().out == f"sift {sift.__version__}\n"


def test_query_syntax_error_exits_3_with_a_caret(
    mini_cli,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_main("search", "a AND") == 3
    err = capsys.readouterr().err
    assert err == "expected a term\n  a AND\n       ^\n"


@pytest.mark.parametrize("command", ["stats", "show 0", "open 0"])
def test_missing_index_dir_exits_4(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    command: str,
) -> None:
    missing = tmp_path / "nope"
    monkeypatch.setenv("SIFT_INDEX", str(missing))
    assert run_main(*command.split()) == 4
    err = capsys.readouterr().err
    assert err == f"sift: no index at {missing}, run 'sift index' first\n"


def test_search_with_missing_index_dir_exits_4(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SIFT_INDEX", str(tmp_path / "nope"))
    assert run_main("search", "rust") == 4


def test_index_dir_without_a_segment_exits_4(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SIFT_INDEX", str(tmp_path))
    assert run_main("search", "chain") == 4


def test_default_index_dir_is_dot_sift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    assert run_main("search", "chain") == 4
    err = capsys.readouterr().err
    assert err == "sift: no index at .sift, run 'sift index' first\n"


def test_sift_error_exits_1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def boom(args: object) -> None:
        raise ConfigError("bad setting")

    monkeypatch.setattr(cli, "run_stats", boom)
    assert run_main("stats") == 1
    assert capsys.readouterr().err == "error: bad setting\n"


def test_group_of_sift_errors_exits_1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def boom(args: object) -> None:
        raise ExceptionGroup(
            "2 files failed", [ConfigError("a"), ConfigError("b")]
        )

    monkeypatch.setattr(cli, "run_stats", boom)
    assert run_main("stats") == 1
    assert capsys.readouterr().err == "error: 2 files failed\n  a\n  b\n"


def test_group_with_a_bug_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(args: object) -> None:
        raise ExceptionGroup("mixed", [ConfigError("a"), KeyError("b")])

    monkeypatch.setattr(cli, "run_stats", boom)
    with pytest.raises(ExceptionGroup, match="mixed"):
        cli.main(["stats"])


def test_python_dash_m_sift_is_the_same_cli() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "sift", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout == f"sift {sift.__version__}\n"


def test_keyboard_interrupt_exits_130_quietly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def boom(args: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_stats", boom)
    assert run_main("stats") == 130
    err = capsys.readouterr().err
    assert err == "interrupted\n"
    assert "Traceback" not in err


def test_index_with_missing_corpus_exits_1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    missing = tmp_path / "posts"
    assert run_main("index", "--corpus", str(missing)) == 1
    err = capsys.readouterr().err
    assert err == f"error: no corpus at {missing}\n"
    assert not (tmp_path / ".sift" / "segment.sft").exists()


def test_bench_index_with_missing_corpus_exits_1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert run_main("bench", "index") == 1
    assert "error: no corpus at corpus/posts" in capsys.readouterr().err


def test_unwritable_log_does_not_fail_the_search(
    mini_cli,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def broken(*args: object) -> None:
        raise SiftError("cannot log the query: secret-query-text")

    monkeypatch.setattr("sift.storage.db.log_query", broken)
    mini_cli.main(["search", "chain"])
    captured = capsys.readouterr()
    assert "1 hits" in captured.out
    assert captured.err.count("\n") == 1
    assert "warning: query not logged" in captured.err
    assert "secret" not in captured.err


def test_read_only_database_does_not_fail_the_search(
    mini_cli, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    db = tmp_path / "idx" / "sift.db"
    db.chmod(0o444)
    try:
        mini_cli.main(["search", "chain"])
    finally:
        db.chmod(0o644)
    captured = capsys.readouterr()
    assert "1 hits" in captured.out
    assert "query not logged" in captured.err


def test_show_reads_one_document(
    mini_cli,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("show must not load every document")

    monkeypatch.setattr(cli, "load_documents", forbidden, raising=False)
    mini_cli.main(["show", "0"])
    assert "title: " in capsys.readouterr().out


def test_limit_above_the_maximum_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as caught:
        cli.main(["search", "--limit", "101", "a"])
    assert caught.value.code == 2
    assert "between 1 and 100" in capsys.readouterr().err


# FastAPI on uvicorn is the default; --raw is the server of chapter 17
SERVERS = pytest.mark.parametrize(
    "flags", [[], ["--raw"]], ids=["fastapi", "raw"]
)


@SERVERS
def test_serve_without_an_index_exits_4(
    flags: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    assert run_main("serve", *flags, "--port", "0") == 4
    assert "run 'sift index' first" in capsys.readouterr().err


@SERVERS
def test_serve_on_a_busy_port_exits_1(
    flags: list[str], mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        assert run_main("serve", *flags, "--port", str(port)) == 1
    err = capsys.readouterr().err
    assert err == (
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
    mini_cli,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setitem(sys.modules, "sift.server.app", None)
    assert run_main("serve", "--port", "0") == 1
    err = capsys.readouterr().err
    assert err.startswith("error: sift serve needs the web extra")
    assert "--raw" in err

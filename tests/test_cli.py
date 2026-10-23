"""Tests for the command line in sift.cli."""

import io
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

import sift
import sift.cli as cli
from sift.document import Document
from sift.errors import ConfigError


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


def test_search_json(mini_cli, capsys: pytest.CaptureFixture[str]) -> None:
    mini_cli.main(["search", "--json", "chain", "tool"])
    data = json.loads(capsys.readouterr().out)
    assert data["total"] == 1
    assert data["hits"][0]["path"].endswith("bicycle-repair.md")
    assert data["hits"][0]["title"] == "Fixing a bicycle chain"


def test_search_no_log_is_accepted(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.main(["search", "--no-log", "chain"])
    assert "hits in 8 files" in capsys.readouterr().out


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
    assert (tmp_path / ".sift" / "docs.json").is_file()
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
    assert out.count("\n") == 3 + 20


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


def test_bench_index_repeats(
    mini_cli, capsys: pytest.CaptureFixture[str]
) -> None:
    mini_cli.main(["bench", "index", "--repeat", "2"])
    assert "2 builds: min " in capsys.readouterr().out


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["search"],
        ["nope"],
        ["bench"],
        ["show", "x"],
        ["search", "--limit", "0", "a"],
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

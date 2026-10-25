"""Compare the ``search`` command of Sift in argparse and in typer.

Both versions take the same words and options as the real command,
parse them and return the values instead of searching. The script
runs them on the same command lines, shows the exit codes of a usage
error, and prints the number of lines each definition takes.
"""

import argparse
import contextlib
import inspect
import io
import sys
from collections.abc import Callable
from typing import Annotated

import typer
from typer.testing import CliRunner

MAX_LIMIT = 100


def limit_arg(text: str) -> int:
    """Convert text to a hit count from 1 to 100, for argparse."""
    try:
        number = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid int: {text!r}") from None
    if not 1 <= number <= MAX_LIMIT:
        raise argparse.ArgumentTypeError(f"not in 1..{MAX_LIMIT}: {text!r}")
    return number


def argparse_search(argv: list[str]) -> dict[str, object]:
    """Parse ``search`` with argparse; return the values."""
    parser = argparse.ArgumentParser(prog="sift")
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("search", help="search the index")
    cmd.add_argument("query", nargs="+", help="query words")
    cmd.add_argument(
        "--limit", type=limit_arg, default=None, help="most hits to print"
    )
    cmd.add_argument("--json", action="store_true", help="print JSON")
    cmd.add_argument("--no-log", action="store_true", help="do not log")
    args = parser.parse_args(argv)
    return {
        "query": args.query,
        "limit": args.limit,
        "json": args.json,
        "no_log": args.no_log,
    }


def typer_limit(text: str) -> int:
    """Convert text to a hit count from 1 to 100, for typer."""
    try:
        number = int(text)
    except ValueError:
        raise typer.BadParameter(f"invalid int: {text!r}") from None
    if not 1 <= number <= MAX_LIMIT:
        raise typer.BadParameter(f"not in 1..{MAX_LIMIT}: {text!r}")
    return number


app = typer.Typer(name="sift", no_args_is_help=True)
RESULT: dict[str, object] = {}


@app.command("search", help="Search the index.")
def typer_search(
    query: Annotated[list[str], typer.Argument(help="Query words.")],
    limit: Annotated[
        int | None,
        typer.Option(parser=typer_limit, help="Most hits to print."),
    ] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print JSON.")
    ] = False,
    no_log: Annotated[
        bool, typer.Option("--no-log", help="Do not log.")
    ] = False,
) -> None:
    """Record the values that typer parsed from the command line."""
    RESULT.update(query=query, limit=limit, json=as_json, no_log=no_log)


@app.command("stats", help="Print statistics.")
def typer_stats() -> None:
    """Exist only so that typer keeps ``search`` as a sub-command."""


def typer_run(argv: list[str]) -> tuple[int, dict[str, object]]:
    """Run the typer app; return the exit code and the parsed values."""
    RESULT.clear()
    result = CliRunner().invoke(app, argv)
    return result.exit_code, dict(RESULT)


def count_lines(*objects: Callable[..., object]) -> tuple[int, int]:
    """Return (all lines, code lines) of the source of objects.

    Code lines leave out blank lines, comments and docstrings.
    """
    total = code = 0
    for obj in objects:
        source = inspect.getsource(obj)
        lines = source.splitlines()
        total += len(lines)
        in_doc = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or in_doc:
                if stripped.count('"""') == 1:
                    in_doc = not in_doc
                continue
            if stripped and not stripped.startswith("#"):
                code += 1
    return total, code


CASES = [
    ["search", "kalman", "filter"],
    ["search", "--limit", "3", "--json", "device", "tree"],
    ["search", "--no-log", "rust"],
    ["search", "--limit", "101", "a"],
    ["search"],
]


def main() -> None:
    """Run both parsers on the same command lines and count lines."""
    for argv in CASES:
        print("$ sift", " ".join(argv))
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                values = argparse_search(argv)
            code_a = 0
        except SystemExit as stop:
            values, code_a = {}, int(stop.code or 0)
        code_t, typed = typer_run(argv)
        print(f"  argparse: exit {code_a}  {values}")
        print(f"  typer   : exit {code_t}  {typed}")
        same = values == typed and code_a == code_t
        print(f"  same: {same}")
    print()
    argp = count_lines(limit_arg, argparse_search)
    typ = count_lines(typer_limit, typer_search)
    print(f"argparse: {argp[0]} lines, {argp[1]} code lines")
    print(f"typer   : {typ[0]} lines, {typ[1]} code lines")
    sys.exit(0)


if __name__ == "__main__":
    main()

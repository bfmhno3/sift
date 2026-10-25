"""Tour rich: markup, Table, Syntax, Panel, Progress, Live, JSON.

Everything is printed on a recording Console of fixed width and saved
as ``out/ch19/rich-tour.svg``; the plain text goes to stdout.
"""

import io
import time
from pathlib import Path

from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress
from rich.syntax import Syntax
from rich.table import Table

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "ch19" / "rich-tour.svg"
CODE = '''\
def search(query: list[str], limit: int | None = None) -> None:
    """Print the best documents for the query."""
    result = searcher.search(" ".join(query), limit or 10)
'''


def tour(console: Console) -> None:
    """Print one of each rich feature on console."""
    console.rule("[bold cyan]rich tour")
    console.print("[bold]bold[/bold] [i]italic[/i] [red on white]red[/]")
    console.print(
        "a [link=https://rich.readthedocs.io]link[/link], :sparkles:"
    )
    table = Table(title="hits", box=box.ROUNDED)
    table.add_column("#", justify="right")
    table.add_column("title", style="cyan")
    table.add_column("score", justify="right")
    table.add_row("1", "Kalman filter, part 2", "8.279")
    table.add_row("2", "The UKF", "7.872")
    console.print(table)
    console.print(Syntax(CODE, "python", line_numbers=True))
    console.print(Panel("Panel text", title="Panel", subtitle="subtitle"))
    with Progress(console=console) as progress:
        task = progress.add_task("indexing", total=20)
        for _ in range(20):
            progress.advance(task)
            time.sleep(0.005)
    with Live(Panel("starting"), console=console, auto_refresh=False) as live:
        for step in ("reading", "analyzing", "writing"):
            live.update(Panel(step, title="live"), refresh=True)
            time.sleep(0.01)
    console.print_json('{"query": "kalman", "total": 5, "hits": [1, 2]}')


def main() -> None:
    """Record the tour, print its text and save the SVG."""
    console = Console(
        file=io.StringIO(),
        width=80,
        force_terminal=True,
        color_system="truecolor",
        record=True,
    )
    tour(console)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(console.export_text(clear=False))
    console.save_svg(str(OUT), title="rich tour")
    print(f"saved {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

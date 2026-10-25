"""Record ``sift search "kalman filter"`` as lab/ch19/ch19-rich-search.svg.

The index is built in a temporary directory, the query is run by the
code of ``sift search`` and printed with the table of ``sift.render``
on a Console of fixed width (100 columns, true colour, recording).
The timings of the real footer are left out so that the file is the
same on every run.

rich 15.0.0 sizes each SVG text element with ``textLength`` from the
number of characters (``len``, console.py line 2534, while the
background rectangles use ``cell_len`` at line 2512). A CJK character
is two cells wide, so the browser squeezes the Chinese titles into
half the width. ``fix_text_length`` rewrites the value from the cell
width.
"""

import html
import io
import re
import tempfile
from pathlib import Path

from rich.cells import cell_len
from rich.console import Console
from rich.text import Text

from sift import render
from sift.analysis import build_pipeline
from sift.config import load_config
from sift.search import Searcher
from sift.storage.store import open_index, update_index

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = Path(__file__).resolve().parent / "ch19-rich-search.svg"
QUERY = "kalman filter"
CHAR_WIDTH = 12.2  # font size 20 times rich's aspect ratio 0.61
TEXT = re.compile(r'<text([^>]*?)textLength="[\d.]+"([^>]*)>([^<]*)</text>')


def fix_text_length(match: re.Match[str]) -> str:
    """Return the element with textLength = cells * CHAR_WIDTH."""
    head, tail, text = match.groups()
    cells = cell_len(html.unescape(text))
    if cells == 0:
        return match.group(0)  # a bare newline: nothing to measure
    length = round(cells * CHAR_WIDTH, 1)
    return f'<text{head}textLength="{length}"{tail}>{text}</text>'


def main() -> None:
    """Build the index, search, and save the SVG."""
    config = load_config()
    console = Console(
        file=io.StringIO(),
        width=100,
        force_terminal=True,
        color_system="truecolor",
        record=True,
    )
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "idx"
        update_index(config.corpus, directory, config.pipeline)
        with open_index(directory) as index:
            searcher = Searcher(
                index,
                k1=config.k1,
                b=config.b,
                pipeline=build_pipeline(index.pipeline_names),
            )
            result = searcher.search(QUERY, config.limit)
            n_docs = index.n_docs
    console.print(Text(f'$ sift search "{QUERY}"', style="bold green"))
    console.print(render.hit_table(result))
    console.print(Text(render.summary_line(result, n_docs), style="dim"))
    print(console.export_text(clear=False), end="")
    svg = console.export_svg(title=f'sift search "{QUERY}"')
    OUT.write_text(TEXT.sub(fix_text_length, svg), encoding="utf-8")
    print(f"saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""Record ``sift search "kalman filter"`` as lab/ch19/ch19-rich-search.svg.

The index is built in a temporary directory, the query is run by the
code of ``sift search`` and printed with the table of ``sift.render``
on a Console of fixed width (100 columns, true colour, recording).
The timings of the real footer are left out so that the file is the
same on every run.
"""

import io
import tempfile
from pathlib import Path

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
    console.save_svg(str(OUT), title=f'sift search "{QUERY}"')
    print(f"saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

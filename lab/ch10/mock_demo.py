"""Replace time.perf_counter with unittest.mock so timings are exact.

Code that measures time is hard to test: the answer changes on every
run. ``patch`` swaps the clock for a mock that returns scripted values,
and the test can check the output and the calls.
"""

import contextlib
import io
from pathlib import Path
from unittest import mock

from sift.analysis import build_pipeline
from sift.corpus import iter_documents
from sift.index import IndexWriter, InvertedIndex
from sift.search import Searcher
from sift.util import timed

MINI = Path("tests/fixtures/mini")


@timed
def work() -> int:
    """Return a value; timed prints how long this took."""
    return 42


def timed_with_a_fake_clock() -> None:
    """Show the decorator's output with a clock that jumps 0.25 s."""
    err = io.StringIO()
    clock = mock.Mock(side_effect=[10.0, 10.25])
    with (
        mock.patch("sift.util.time.perf_counter", clock),
        contextlib.redirect_stderr(err),
    ):
        value = work()
    print(f"value={value}, stderr={err.getvalue()!r}")
    print(f"clock calls: {clock.call_count}")
    clock.assert_called_with()


def search_with_a_fake_clock() -> None:
    """Make Searcher.search report a took_ms of exactly 125."""
    index = InvertedIndex()
    with IndexWriter(index, build_pipeline()) as writer:
        for doc in iter_documents(MINI):
            writer.add(doc)
    searcher = Searcher(index)
    with mock.patch("sift.search.time.perf_counter") as clock:
        clock.side_effect = [1.0, 1.125]
        result = searcher.search("chain")
    print(f"took_ms={result.took_ms}, hits={len(result.hits)}")


def spying_on_a_method() -> None:
    """Count calls to a real method with ``wraps``."""
    pipeline = build_pipeline()
    with mock.patch.object(pipeline, "terms", wraps=pipeline.terms) as spy:
        pipeline.terms("tea ceremony")
        pipeline.terms("river")
    print(f"terms called {spy.call_count} times: {spy.call_args_list}")


def mock_that_cannot_lie() -> None:
    """Show autospec: a mock with the signature of the real thing."""
    fake = mock.create_autospec(build_pipeline().terms)
    fake.return_value = ["x"]
    print(f"autospec call: {fake('anything')}")
    try:
        # BAD: a plain Mock would accept this call without complaint
        # error: TypeError: missing a required argument: 'text'
        fake()
    except TypeError as error:
        print(f"TypeError: {error}")


def main() -> None:
    """Run the four demonstrations."""
    timed_with_a_fake_clock()
    search_with_a_fake_clock()
    spying_on_a_method()
    mock_that_cannot_lie()


if __name__ == "__main__":
    main()

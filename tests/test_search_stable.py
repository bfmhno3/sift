"""The top 10 of every bench query over the full corpus stays put.

The ids were taken before the chapter 23 optimizations. Any change
to tokenizing, indexing or scoring that moves a document in these
lists is a change of behavior, not a speedup.
"""

from pathlib import Path

import pytest

from sift.analysis import Pipeline, build_pipeline
from sift.corpus import iter_documents
from sift.index import IndexWriter, InvertedIndex
from sift.search import Searcher

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "corpus" / "posts"
QUERIES = ROOT / "bench" / "queries.txt"
PIPELINE = ("mixed", "nfkc", "stopwords")

TOP10: dict[str, list[int]] = {
    "rust 所有权": [78, 79, 85, 84, 82, 80, 89, 91, 86, 90],
    "kalman filter": [15, 20, 19, 14, 21],
    '"device tree"': [7, 115, 113, 112],
    "pid AND 积分": [69, 74, 65, 71, 68, 73, 72, 70, 67, 66],
    "tag:Rust lifetime": [81, 79, 89, 91],
    "矩阵 OR matrix": [73, 40, 26, 104, 18, 25, 34, 52, 51, 109],
    "typst -latex": [110, 96, 108, 99, 98, 105, 109, 107, 103, 106],
    "cmake vcpkg": [116, 77, 78],
    "gdb 断点": [10, 115, 0],
    "linux kernel module": [112, 115],
    "奇异值": [109, 57, 32, 53, 56, 29, 30, 36, 33, 52],
    "owner*": [115, 94, 79, 81, 86, 91],
}

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not CORPUS.is_dir(), reason="run `make corpus` first"),
]


@pytest.fixture(scope="module")
def pipeline() -> Pipeline:
    """Return the pipeline of sift.toml."""
    return build_pipeline(PIPELINE)


@pytest.fixture(scope="module")
def searcher(pipeline: Pipeline) -> Searcher:
    """Return a Searcher over an index of the full corpus."""
    index = InvertedIndex()
    with IndexWriter(index, pipeline) as writer:
        for doc in iter_documents(CORPUS):
            writer.add(doc)
    return Searcher(index, pipeline=pipeline)


def test_every_bench_query_is_pinned() -> None:
    queries = QUERIES.read_text(encoding="utf-8").splitlines()
    assert [q for q in queries if q] == list(TOP10)


@pytest.mark.parametrize("query", list(TOP10))
def test_top10_doc_ids(searcher: Searcher, query: str) -> None:
    result = searcher.search(query, 10)
    assert [hit.doc_id for hit in result.hits] == TOP10[query]

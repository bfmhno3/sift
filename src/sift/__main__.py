"""Index search: python -m sift search <word>... | python -m sift stats."""

import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator
from operator import itemgetter
from pathlib import Path

from sift.analysis.tokenize import iter_tokens, tokenize
from sift.corpus import iter_documents
from sift.index import build_index
from sift.markdown import split_front_matter, strip_markdown
from sift.scoring import tf_idf
from sift.util import compose, timed

CORPUS = Path("corpus/posts")
USAGE = "usage: python -m sift search <word>... | python -m sift stats"


def iter_terms(text: str) -> Iterator[str]:
    """Yield the term of each token of text."""
    return (token.text for token in iter_tokens(text))


# 文件文本 -> 去掉 front matter -> 去掉 Markdown 标记 -> 词项流
analyze_file = compose(
    split_front_matter, itemgetter(1), strip_markdown, iter_terms
)


@timed
def load_index(root: Path) -> tuple[list[Path], dict[str, dict[int, int]]]:
    """Read, tokenize and index every Markdown file under root.

    The doc_id of a file is its position in the sorted path list.
    """
    paths: list[Path] = []

    def analyzed() -> Iterator[tuple[int, Iterator[str]]]:
        for doc_id, doc in enumerate(iter_documents(root)):
            paths.append(doc.path)
            yield doc_id, analyze_file(doc.text)

    return paths, build_index(analyzed())


def search_index(
    index: dict[str, dict[int, int]],
    words: list[str],
    n_docs: int,
    scoring: Callable[[int, int, int], float] = tf_idf,
) -> list[tuple[float, int]]:
    """Return (score, doc_id) of documents holding every query token.

    A document scores the sum over query terms of
    ``scoring(tf, df, n_docs)``. Sorted by score descending, then
    doc_id.
    """
    terms = list(dict.fromkeys(token for w in words for token in tokenize(w)))
    if not terms:
        return []
    postings = [index.get(term, {}) for term in terms]
    matching = set(postings[0])
    for posting in postings[1:]:
        matching &= posting.keys()
    hits = [
        (sum(scoring(p[doc_id], len(p), n_docs) for p in postings), doc_id)
        for doc_id in matching
    ]
    hits.sort(key=lambda hit: (-hit[0], hit[1]))
    return hits


def run_search(words: list[str]) -> None:
    """Print the top 10 files by TF-IDF holding every word."""
    start = time.perf_counter()
    paths, index = load_index(CORPUS)
    built = time.perf_counter()
    hits = search_index(index, words, len(paths))
    end = time.perf_counter()
    for score, doc_id in hits[:10]:
        print(f"{score:8.3f}  {paths[doc_id]}")
    print(
        f"{len(hits)} hits in {len(paths)} files: "
        f"index built in {(built - start) * 1000:.1f} ms, "
        f"query took {(end - built) * 1000:.3f} ms"
    )


def run_stats() -> None:
    """Print document count, vocabulary size and the 20 top terms."""
    start = time.perf_counter()
    paths, index = load_index(CORPUS)
    built = time.perf_counter()
    totals = Counter({term: sum(p.values()) for term, p in index.items()})
    print(f"documents: {len(paths)}")
    print(f"vocabulary: {len(index)}")
    for term, count in totals.most_common(20):
        print(f"{count:>7}  {term}")
    print(f"index built in {(built - start) * 1000:.1f} ms")


def main() -> None:
    """Dispatch the subcommand given on the command line."""
    args = sys.argv[1:]
    if args[:1] == ["search"] and len(args) > 1:
        run_search(args[1:])
    elif args == ["stats"]:
        run_stats()
    else:
        sys.exit(USAGE)


if __name__ == "__main__":
    main()

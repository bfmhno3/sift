"""Index search: python -m sift search <word>... | python -m sift stats."""

import sys
import time
from collections import Counter
from pathlib import Path

from sift.analysis.tokenize import tokenize
from sift.index import build_index
from sift.markdown import split_front_matter, strip_markdown

CORPUS = Path("corpus/posts")
USAGE = "usage: python -m sift search <word>... | python -m sift stats"


def load_index(root: Path) -> tuple[list[Path], dict[str, dict[int, int]]]:
    """Read, tokenize and index every Markdown file under root.

    The doc_id of a file is its position in the sorted path list.
    """
    paths = sorted(root.glob("*.md"))
    docs: dict[int, list[str]] = {}
    for doc_id, path in enumerate(paths):
        text = path.read_text(encoding="utf-8")
        body = strip_markdown(split_front_matter(text)[1])
        docs[doc_id] = tokenize(body)
    return paths, build_index(docs)


def search_index(
    index: dict[str, dict[int, int]], words: list[str]
) -> list[tuple[int, int]]:
    """Return (summed tf, doc_id) of documents holding every query token.

    Sorted by summed tf descending, then doc_id.
    """
    terms = list(dict.fromkeys(token for w in words for token in tokenize(w)))
    if not terms:
        return []
    postings = [index.get(term, {}) for term in terms]
    matching = set(postings[0])
    for posting in postings[1:]:
        matching &= posting.keys()
    hits = [(sum(p[doc_id] for p in postings), doc_id) for doc_id in matching]
    hits.sort(key=lambda hit: (-hit[0], hit[1]))
    return hits


def run_search(words: list[str]) -> None:
    """Print the top 10 files holding every word."""
    start = time.perf_counter()
    paths, index = load_index(CORPUS)
    built = time.perf_counter()
    hits = search_index(index, words)
    end = time.perf_counter()
    for count, doc_id in hits[:10]:
        print(f"{count:>6}  {paths[doc_id]}")
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

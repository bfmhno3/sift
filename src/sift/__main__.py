"""Naive full-text search: python -m sift <word> [<word>...]."""

import sys
import time
from collections import Counter
from pathlib import Path

from sift.analysis.tokenize import tokenize
from sift.markdown import split_front_matter, strip_markdown

CORPUS = Path("corpus/posts")


def count_words(text: str, words: list[str]) -> int:
    """Return how many tokens of text exactly equal a query token."""
    wanted = {token for word in words for token in tokenize(word)}
    counts = Counter(tokenize(strip_markdown(split_front_matter(text)[1])))
    return sum(counts[token] for token in wanted)


def search(root: Path, words: list[str]) -> tuple[list[tuple[int, Path]], int]:
    """Scan every Markdown file under root.

    Return the hits as (count, path) sorted by count descending, then
    path, together with the number of files scanned.
    """
    hits: list[tuple[int, Path]] = []
    n_files = 0
    for path in sorted(root.glob("*.md")):
        n_files += 1
        count = count_words(path.read_text(encoding="utf-8"), words)
        if count:
            hits.append((count, path))
    hits.sort(key=lambda hit: (-hit[0], hit[1]))
    return hits, n_files


def main() -> None:
    """Print the top 10 files for the words given on the command line."""
    words = sys.argv[1:]
    if not words:
        sys.exit("usage: python -m sift <word> [<word>...]")
    start = time.perf_counter()
    hits, n_files = search(CORPUS, words)
    elapsed_ms = (time.perf_counter() - start) * 1000
    for count, path in hits[:10]:
        print(f"{count:>6}  {path}")
    print(f"searched {n_files} files in {elapsed_ms:.1f} ms")


if __name__ == "__main__":
    main()

"""Naive full-text search: python -m sift <word> [<word>...]."""

import sys
import time
from pathlib import Path

CORPUS = Path("corpus/posts")


def count_words(text: str, words: list[str]) -> int:
    """Return the total case-insensitive occurrences of words in text."""
    lowered = text.lower()
    return sum(lowered.count(word) for word in words)


def search(root: Path, words: list[str]) -> tuple[list[tuple[int, Path]], int]:
    """Scan every Markdown file under root.

    Return the hits as (count, path) sorted by count descending, then
    path, together with the number of files scanned.
    """
    lowered = [word.lower() for word in words]
    hits: list[tuple[int, Path]] = []
    n_files = 0
    for path in sorted(root.glob("*.md")):
        n_files += 1
        count = count_words(path.read_text(encoding="utf-8"), lowered)
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

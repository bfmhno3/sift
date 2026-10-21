"""Lazy pipeline: file -> lines -> tokens -> counts, peak memory."""

import itertools
import time
import tracemalloc
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from sift.analysis.tokenize import iter_tokens, tokenize

ROOT = Path("corpus/posts")


def paths() -> Iterator[Path]:
    """Yield the corpus files in sorted order (rglob is lazy)."""
    return iter(sorted(ROOT.rglob("*.md")))


def lines(path: Path) -> Iterator[str]:
    """Yield the lines of one file; the file object is the iterator."""
    with path.open(encoding="utf-8") as handle:
        yield from handle


def terms() -> Iterator[str]:
    """Yield the term of every token of every line of every file."""
    all_lines = itertools.chain.from_iterable(map(lines, paths()))
    for line in all_lines:
        for token in iter_tokens(line):
            yield token.text


def count_lazy() -> Counter[str]:
    """Count terms through the lazy pipeline."""
    return Counter(terms())


def count_eager() -> Counter[str]:
    """Read every file whole and build the full token list first."""
    texts = [path.read_text(encoding="utf-8") for path in paths()]
    all_tokens = [t for text in texts for t in tokenize(text)]
    return Counter(all_tokens)


def measure(label: str, work) -> Counter[str]:
    """Run work under tracemalloc and print its peak, then its time."""
    tracemalloc.start()
    counts = work()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    start = time.perf_counter()
    work()
    elapsed = (time.perf_counter() - start) * 1000
    print(f"{label:6} peak {peak / 1024:9.0f} KiB, {elapsed:7.0f} ms")
    return counts


def main() -> None:
    """Compare the lazy pipeline with the eager one."""
    print("first 5 lines of the first file:")
    for line in itertools.islice(lines(next(paths())), 5):
        print("  ", line.rstrip())
    lazy = measure("lazy", count_lazy)
    eager = measure("eager", count_eager)
    print("same counts:", lazy == eager)
    print("tokens:", lazy.total(), "distinct:", len(lazy))
    print("top 5:", lazy.most_common(5))


if __name__ == "__main__":
    main()

"""bisect: binary search in a sorted list, and a prefix range."""

from bisect import bisect_left, bisect_right, insort
from pathlib import Path

from sift.analysis import build_pipeline
from sift.corpus import iter_documents
from sift.index import InvertedIndex

MINI = Path("tests/fixtures/mini")
TERMS = ["owner", "ownership", "owns", "oxide", "rust", "rustc"]


def main() -> None:
    """Show insertion points, insort and prefix lookup."""
    scores = [10, 20, 20, 20, 30]
    print("scores", scores)
    print("bisect_left(20) =", bisect_left(scores, 20))
    print("bisect_right(20) =", bisect_right(scores, 20))
    print("count of 20 =", bisect_right(scores, 20) - bisect_left(scores, 20))
    insort(scores, 25)
    print("after insort(25):", scores)
    people = [("ann", 3), ("bob", 5), ("cy", 8)]
    print("key=:", bisect_left(people, 4, key=lambda p: p[1]))
    lo = bisect_left(TERMS, "owner")
    hi = bisect_left(TERMS, "owner" + "\U0010ffff")
    print("terms with prefix 'owner':", TERMS[lo:hi])
    pipeline = build_pipeline()
    index = InvertedIndex()
    for doc in iter_documents(MINI):
        index.add(doc, pipeline.analyze(doc.body))
    print("mini corpus vocabulary:", len(index))
    for prefix in ("tea", "bicycle", "zzz"):
        found = index.terms_with_prefix(prefix)
        print(f"terms_with_prefix({prefix!r}) = {found}")


if __name__ == "__main__":
    main()

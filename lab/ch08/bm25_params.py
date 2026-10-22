"""How k1 and b change the top 3 for one query."""

from itertools import product

from sift.analysis import build_pipeline
from sift.cli import CORPUS, load_index
from sift.search import Searcher

QUERY = "kalman filter"
K1S = (0.5, 1.2, 2.0)
BS = (0, 0.75, 1)


def main() -> None:
    """Print the top 3 documents for every (k1, b) pair."""
    pipeline = build_pipeline()
    _, index = load_index(CORPUS, pipeline)
    print(f"query {QUERY!r}")
    for k1, b in product(K1S, BS):
        searcher = Searcher(index, k1=k1, b=b, pipeline=pipeline)
        hits = searcher.search(QUERY, limit=3).hits
        names = ", ".join(f"{h.path.stem[:28]} {h.score:.2f}" for h in hits)
        print(f"k1={k1:<3} b={b:<4} {names}")


if __name__ == "__main__":
    main()

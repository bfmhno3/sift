"""BM25 for one query and one document, every factor printed."""

import math

from sift.analysis import build_pipeline
from sift.cli import CORPUS, load_index
from sift.scoring import bm25
from sift.search import Searcher

QUERY = "kalman filter"
K1, B = 1.2, 0.75


def main() -> None:
    """Recompute the score of the top hit by hand and compare."""
    pipeline = build_pipeline()
    _, index = load_index(CORPUS, pipeline)
    top = Searcher(index, pipeline=pipeline).search(QUERY, limit=1).hits[0]
    n_docs, avg_len = index.n_docs, index.avg_doc_len
    doc_len = index.doc_len(top.doc_id)
    norm = 1 - B + B * doc_len / avg_len
    print(f"query {QUERY!r}, document {top.path.name}")
    print(f"N = {n_docs}, avgdl = {avg_len:.2f}, dl = {doc_len}")
    print(f"k1 = {K1}, b = {B}, norm = 1 - b + b * dl / avgdl = {norm:.4f}")
    total = 0.0
    for term in pipeline.terms(QUERY):
        plist = index[term]
        df = len(plist)
        tf = next(p.tf for p in plist if p.doc_id == top.doc_id)
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        sat = tf * (K1 + 1) / (tf + K1 * norm)
        score = idf * sat
        total += score
        print(f"term {term!r}: tf = {tf}, df = {df}")
        print(f"  idf = ln(1 + (N - df + 0.5) / (df + 0.5)) = {idf:.4f}")
        print(f"  tf * (k1 + 1) / (tf + k1 * norm) = {sat:.4f}")
        print(f"  idf * that = {score:.4f}")
        print(f"  bm25() says {bm25(tf, df, doc_len, avg_len, n_docs):.4f}")
    print(f"sum = {total:.6f}, Searcher score = {top.score:.6f}")
    assert math.isclose(total, top.score)


if __name__ == "__main__":
    main()

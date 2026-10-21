"""Top 3 by plain tf and by TF-IDF; idf cache hit rate on the corpus."""

from sift.__main__ import CORPUS, load_index, search_index
from sift.scoring import idf

QUERIES = ["linux device", "矩阵 matrix", "python function"]


def plain_tf(tf: int, df: int, n_docs: int) -> float:
    """Score a term by its raw frequency, ignoring df."""
    return tf


def main() -> None:
    """Compare the two rankings, then report idf cache statistics."""
    paths, index = load_index(CORPUS)
    n_docs = len(paths)
    idf.cache_clear()
    for query in QUERIES:
        words = query.split()
        by_tf = search_index(index, words, n_docs, plain_tf)
        by_idf = search_index(index, words, n_docs)
        print(f"query: {query!r}: {len(by_idf)} hits")
        print("  plain tf")
        for score, doc_id in by_tf[:3]:
            print(f"    {score:8.0f}  {paths[doc_id].name}")
        print("  tf-idf")
        for score, doc_id in by_idf[:3]:
            print(f"    {score:8.3f}  {paths[doc_id].name}")
    info = idf.cache_info()
    calls = info.hits + info.misses
    print(info)
    print(f"idf calls {calls}, hit rate {info.hits / calls:.4%}")


if __name__ == "__main__":
    main()

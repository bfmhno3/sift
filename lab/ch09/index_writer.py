"""IndexWriter: all documents of a block, or none of them."""

from pathlib import Path

from sift.analysis import build_pipeline
from sift.corpus import iter_documents
from sift.index import IndexWriter, InvertedIndex

MINI = Path("tests/fixtures/mini")


def main() -> None:
    """Add documents in two blocks; the second one fails."""
    docs = list(iter_documents(MINI))
    index = InvertedIndex()
    pipeline = build_pipeline()

    with IndexWriter(index, pipeline) as writer:
        for doc in docs[:3]:
            writer.add(doc)
    print("after a good block:", index.n_docs, "docs,", len(index), "terms")
    before = (index.n_docs, len(index), len(index.title_index))

    try:
        with IndexWriter(index, pipeline) as writer:
            for doc in docs[3:6]:
                writer.add(doc)
            print("inside the block:", index.n_docs, "docs")
            raise RuntimeError("disk full")
    except RuntimeError as exc:
        print("the exception still escapes:", exc)
    after = (index.n_docs, len(index), len(index.title_index))
    print("rolled back:", after == before, after)

    with IndexWriter(index, pipeline) as writer:
        writer.add(docs[3])
    print("a later block works:", index.n_docs, "docs")

    try:
        with IndexWriter(index, pipeline) as writer:
            writer.add(docs[3])
    except ValueError as exc:
        # error: ValueError: doc_id 3 is already indexed
        print("duplicate id:", exc)
    print("doc 3 kept by the failed block:", 3 in index.documents)


if __name__ == "__main__":
    main()

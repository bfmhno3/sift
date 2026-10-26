"""The five most similar posts to three posts, by TF-IDF cosine."""

from sift.analysis import build_pipeline
from sift.analytics.vectors import similar, top_pairs
from sift.cli import load_index
from sift.config import load_config

POSTS = (
    "kalman-filter-05-ekf.md",
    "rust-by-pebble-02-ownership.md",
    "typst-by-xuan-01-first-document.md",
)


def main() -> None:
    """List neighbours for some posts, then the closest pairs."""
    config = load_config()
    documents, index = load_index(
        config.corpus, build_pipeline(config.pipeline)
    )
    by_name = {doc.path.name: doc for doc in documents}
    for name in POSTS:
        doc = by_name.get(name)
        if doc is None:
            print(f"{name}: not in the corpus")
            continue
        print(f"\n{doc.title} (id {doc.doc_id})")
        for other, score in similar(index, doc.doc_id, 5)[1:]:
            print(f"  {score:.3f}  {index.documents[other].title}")
    print("\nclosest pairs in the corpus")
    for first, second, score in top_pairs(index, 5):
        titles = index.documents[first].title, index.documents[second].title
        print(f"  {score:.3f}  {titles[0]}  <->  {titles[1]}")


if __name__ == "__main__":
    main()

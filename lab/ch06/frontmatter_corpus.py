"""Parse the front matter of every post and count categories, tags."""

from collections import Counter
from pathlib import Path

from sift.corpus import iter_documents
from sift.errors import FrontMatterError
from sift.frontmatter import parse_front_matter
from sift.markdown import split_front_matter

CORPUS = Path("corpus/posts")
MINI = Path("tests/fixtures/mini")

BAD = [
    "title: ok\ntitle: again",
    'title: "unterminated',
    "tags:\n  - a\nkey",
    "  - orphan item",
    "nested:\n    key: value",
    "empty:",
    "note: >> folded",
]


def main() -> None:
    """Parse the corpus and the mini fixtures, then bad inputs."""
    raw_keys: Counter[str] = Counter()
    n_raw = 0
    for path in sorted(CORPUS.glob("*.md")):
        front = split_front_matter(path.read_text(encoding="utf-8"))[0]
        raw_keys.update(list(parse_front_matter(front)))
        n_raw += 1
    print("front matter parsed:", n_raw)
    print("keys:", dict(sorted(raw_keys.items())))

    docs = list(iter_documents(CORPUS))
    print("documents:", len(docs))
    print("with series:", sum(d.series is not None for d in docs))
    print("with updated:", sum(d.updated is not None for d in docs))
    print("posts per category:")
    categories = Counter(d.category for d in docs)
    for name, count in sorted(
        categories.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        print(f"  {count:4}  {name}")
    tags = Counter(tag for d in docs for tag in d.tags)
    print("distinct tags:", len(tags), "uses:", tags.total())
    print("top 15 tags:")
    for name, count in sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))[
        :15
    ]:
        print(f"  {count:4}  {name}")

    mini = list(iter_documents(MINI))
    print("mini fixtures:", len(mini))
    for d in mini:
        print(f"  {d.doc_id} {d.path.name:22} {d.category} {d.tags}")

    print("bad inputs:")
    for text in BAD:
        try:
            parse_front_matter(text)
        except FrontMatterError as exc:
            print(f"  {text!r:36} -> FrontMatterError: {exc}")
        else:
            print(f"  {text!r:36} -> parsed (unexpected)")


if __name__ == "__main__":
    main()

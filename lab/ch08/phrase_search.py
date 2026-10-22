"""Phrase search: intersect positions, not only documents."""

from sift.__main__ import CORPUS, load_index
from sift.analysis import build_pipeline
from sift.query import evaluate, parse

PHRASE = '"device tree"'
NAME = "devicetree-study-notes.md"


def main() -> None:
    """Compare AND with a phrase and show the positions behind it."""
    pipeline = build_pipeline()
    documents, index = load_index(CORPUS, pipeline)
    both = evaluate(parse("device tree"), index, pipeline)
    phrase = evaluate(parse(PHRASE), index, pipeline)
    print(f"device AND tree: {len(both)} documents")
    print(f"{PHRASE}: {len(phrase)} documents")
    reverse = evaluate(parse('"tree device"'), index, pipeline)
    print(f'"tree device": {len(reverse)} documents (order matters)')
    doc_id = next(d.doc_id for d in documents if d.path.name == NAME)
    for word in ("device", "tree"):
        posting = next(p for p in index[word] if p.doc_id == doc_id)
        print(f"{word!r} in {NAME}: tf {posting.tf}")
        print("  positions", posting.positions[:12], "...")
    posting = next(p for p in phrase if p.doc_id == doc_id)
    print("phrase start positions", posting.positions[:12], "...")
    start = posting.positions[0]
    print(
        "tokens there:",
        [
            t.text
            for t in pipeline.analyze(documents[doc_id].body)
            if start - 2 <= t.position <= start + 3
        ],
    )
    cjk = evaluate(parse('"所有权"'), index, pipeline)
    print(f'"所有权" is the bigram phrase 所有 + 有权: {len(cjk)} documents')


if __name__ == "__main__":
    main()

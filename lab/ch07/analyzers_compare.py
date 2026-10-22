"""Latin-only, CJK-bigram and mixed analyzers on the same 3 posts."""

from pathlib import Path

from sift.analysis import REGISTRY, build_pipeline
from sift.corpus import iter_documents

CORPUS = Path("corpus/posts")
POSTS = (
    "notes-of-effective-cmake.md",
    "vmware-keyboard-lag-fix.md",
    "understanding-logic-of-concession.md",
)
SAMPLE = 8


def vocabulary(name: str) -> tuple[int, int]:
    """Return (distinct terms, tokens) of the whole corpus."""
    pipeline = build_pipeline([name, "nfkc"])
    terms: set[str] = set()
    count = 0
    for doc in iter_documents(CORPUS):
        for token in pipeline.analyze(doc.body):
            terms.add(token.text)
            count += 1
    return len(terms), count


def main() -> None:
    """Print counts and samples per post, then corpus vocabularies."""
    docs = {d.path.name: d for d in iter_documents(CORPUS)}
    for post in POSTS:
        body = docs[post].body
        print(f"== {post} ({len(body)} chars)")
        for name in REGISTRY:
            terms = build_pipeline([name, "nfkc"]).terms(body)
            print(f"{name:11} {len(terms):6} tokens  {terms[:SAMPLE]}")
    print("== whole corpus, tokenizer + nfkc")
    print(f"{'analyzer':11} {'vocabulary':>10} {'tokens':>8}")
    for name in REGISTRY:
        vocab, tokens = vocabulary(name)
        print(f"{name:11} {vocab:>10} {tokens:>8}")
    print("registry:", list(REGISTRY))


if __name__ == "__main__":
    main()

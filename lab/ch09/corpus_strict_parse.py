"""Count the corpus files the strict front matter parser rejects."""

from pathlib import Path

from sift.corpus import iter_documents

CORPUS = Path("corpus/posts")


def main() -> None:
    """Parse every post with keep_going and count the failures."""
    parsed = 0
    failed: list[BaseException] = []
    try:
        for _ in iter_documents(CORPUS):
            parsed += 1
    except ExceptionGroup as group:
        failed = list(group.exceptions)
    files = len(list(CORPUS.rglob("*.md")))
    print(f"files:  {files}")
    print(f"failed: {len(failed)}")
    for error in failed:
        print(f"  {error}")
    print(f"parsed: {parsed}")


if __name__ == "__main__":
    main()

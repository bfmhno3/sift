"""BaseException.add_note: context that travels with the error."""

import traceback
from pathlib import Path

from sift.document import Document
from sift.errors import SiftError

MINI = Path("tests/fixtures/mini")


def read_all(root: Path) -> None:
    """Parse every file, annotating the failure with its path."""
    for doc_id, path in enumerate(sorted(root.glob("*.md"))):
        text = path.read_text(encoding="utf-8")
        text = text.replace("title:", "title: [", 1) if doc_id == 3 else text
        try:
            Document.from_markdown(doc_id, path, text)
        except SiftError as exc:
            exc.add_note(f"while reading file {doc_id}: {path.name}")
            exc.add_note("try the file in an editor first")
            raise


def main() -> None:
    """Show __notes__ and how a traceback prints them."""
    try:
        read_all(MINI)
    except Exception as exc:
        print("type:", type(exc).__name__)
        print("__notes__:", exc.__notes__)
        print("--- format_exception_only:")
        for line in traceback.format_exception_only(exc):
            print(line, end="")

    err = ValueError("plain")
    print("no notes yet:", hasattr(err, "__notes__"))
    err.add_note("first")
    err.add_note("second")
    print("after two notes:", err.__notes__)
    try:
        err.add_note(42)
    except TypeError as exc:
        # error: TypeError: add_note() argument must be str, not int
        print("non-str note:", exc)


if __name__ == "__main__":
    main()

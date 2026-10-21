"""Tokenize the corpus: sizes, token counts and the top tokens."""

from collections import Counter
from pathlib import Path

from sift.analysis.tokenize import tokenize
from sift.markdown import split_front_matter, strip_markdown

ROOT = Path("corpus/posts")
SAMPLES = (
    "kalman-filter-01-one-dimension.md",
    "gdb-debugging-guide.md",
    "grep-ripgrep-search-guide.md",
)


def main() -> None:
    """Print sizes and token counts."""
    chars = 0
    size = 0
    tokens: list[str] = []
    for path in sorted(ROOT.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        chars += len(text)
        size += len(text.encode("utf-8"))
        tokens.extend(tokenize(strip_markdown(split_front_matter(text)[1])))
    print(f"files: {len(list(ROOT.glob('*.md')))}")
    print(
        f"characters: {chars}, bytes: {size}, bytes/char: {size / chars:.3f}"
    )
    print(f"tokens: {len(tokens)}, distinct: {len(set(tokens))}")
    for name in SAMPLES:
        text = (ROOT / name).read_text(encoding="utf-8")
        body = strip_markdown(split_front_matter(text)[1])
        raw = tokenize(text)
        print(f"{name}: {len(raw)} raw, {len(tokenize(body))} stripped")
    for token, n in sorted(
        Counter(tokens).items(), key=lambda kv: (-kv[1], kv[0])
    )[:15]:
        print(f"{n:>7}  {token}")


if __name__ == "__main__":
    main()

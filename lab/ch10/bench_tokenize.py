"""pytest-benchmark: how fast is the tokenizer?

This file holds pytest tests, so it lives under lab/ and the normal
``pytest`` run (testpaths = tests src) never collects it. Run it with
its own path, which ``extra.sh`` does::

    pytest lab/ch10/bench_tokenize.py --benchmark-only

Running the file with python3 does the same through ``pytest.main``.
"""

import sys
from pathlib import Path

import pytest

from sift.analysis import build_pipeline, iter_tokens, tokenize

POSTS = Path("corpus/posts")
MINI = Path("tests/fixtures/mini")


def sample_text() -> str:
    """Return about 100 KB of text: posts if present, else fixtures."""
    root = POSTS if POSTS.is_dir() else MINI
    parts: list[str] = []
    size = 0
    for path in sorted(root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        parts.append(text)
        size += len(text)
        if size > 100_000:
            break
    return "\n".join(parts)


@pytest.fixture(scope="module")
def text() -> str:
    """Return the benchmark input, built once per module."""
    return sample_text()


def test_tokenize_to_list(benchmark, text: str) -> None:
    terms = benchmark(tokenize, text)
    assert terms


def test_iter_tokens_consumed(benchmark, text: str) -> None:
    def consume() -> int:
        return sum(1 for _ in iter_tokens(text))

    assert benchmark(consume) > 0


def test_default_pipeline_terms(benchmark, text: str) -> None:
    pipeline = build_pipeline()
    assert benchmark(pipeline.terms, text)


def test_latin_only_pipeline_terms(benchmark, text: str) -> None:
    pipeline = build_pipeline(["latin", "nfkc"])
    assert benchmark(pipeline.terms, text)


def main() -> None:
    """Run this file's benchmarks with pytest."""
    code = pytest.main(
        [
            __file__,
            "-c",
            "/dev/null",
            "-p",
            "no:cacheprovider",
            "--benchmark-only",
            "--benchmark-columns=min,median,max,rounds",
            "--benchmark-max-time=0.2",
            "--benchmark-disable-gc",
        ]
    )
    sys.exit(code)


if __name__ == "__main__":
    main()

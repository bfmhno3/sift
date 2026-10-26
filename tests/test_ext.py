"""Tests for sift.ext: the native tokenizers against the Python one.

They need the artifacts of ``make ext`` and ``make ext-rs`` and skip
when one is missing.
"""

import ctypes
import errno
import re
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sift.analysis import build_pipeline
from sift.analysis.tokenize import CJK, Token, fold, iter_tokens

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "corpus" / "posts"
MINI = Path(__file__).parent / "fixtures" / "mini"

TOKENIZER_MODULES = [
    "sift.ext.ctok",
    "sift.ext.cffitok",
    "sift.ext._cytok",
    "sift.ext.rs",
]
COUNTER_MODULES = [
    "sift.ext.ctok",
    "sift.ext.cffitok",
    "sift.ext._cytok",
    "sift.ext._capi",
]
ANALYZERS = {
    "sift.ext.ctok": "mixed-c",
    "sift.ext.cffitok": "mixed-cffi",
    "sift.ext._cytok": "mixed-cython",
    "sift.ext.rs": "mixed-rust",
}

EDGE_TEXTS = [
    "",
    "a",
    "c++ c# c+++ c## a_b 9+",
    "The Fox ran. 搜索引擎 and 中",
    "中a文",
    "ﬁ ㎏ ｃ＋＋ Ｒｕｓｔ",
    "𠀀 emoji 😀 中文😀中文",
    "lone \ud800 surrogate 中\udfff文 \ud83d",
    "nul\x00byte 中\x00文",
    "\u3400\u4dbf\u4dc0\u4e00\u9fff\ua000\uf900\ufaff\ufb00",
    "é ü ß 中é文",
    "x" * 70000 + "中" * 70000,
]


def python_tokens(text: str) -> list[Token]:
    """Return what the Python tokenizer gives for text."""
    return list(iter_tokens(text))


Loader = Callable[[str], ModuleType]


def native_tokens(load: Loader, name: str) -> Callable[[str], list[Token]]:
    """Return text -> tokens for the module name, folding like Python."""
    module = load(name)

    def run(text: str) -> list[Token]:
        tokens: list[Token] = module.tokens(fold(text))
        return tokens

    return run


@pytest.mark.parametrize("name", TOKENIZER_MODULES)
@pytest.mark.parametrize("text", EDGE_TEXTS)
def test_edge_texts_give_the_python_tokens(
    name: str, text: str, native: Loader
) -> None:
    assert native_tokens(native, name)(text) == python_tokens(text)


@pytest.mark.parametrize("name", TOKENIZER_MODULES)
@pytest.mark.parametrize(
    "path", sorted(MINI.glob("*.md")), ids=lambda p: p.name
)
def test_mini_fixtures_give_the_python_tokens(
    name: str, path: Path, native: Loader
) -> None:
    text = path.read_text(encoding="utf-8")
    assert native_tokens(native, name)(text) == python_tokens(text)


@pytest.mark.slow
@pytest.mark.skipif(not CORPUS.is_dir(), reason="run `make corpus` first")
@pytest.mark.parametrize("name", TOKENIZER_MODULES)
def test_corpus_gives_the_python_tokens(name: str, native: Loader) -> None:
    run = native_tokens(native, name)
    for path in sorted(CORPUS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        assert run(text) == python_tokens(text), path.name


@pytest.mark.parametrize("name", TOKENIZER_MODULES)
@given(text=st.text(st.characters(exclude_categories=()), max_size=300))
def test_any_text_gives_the_python_tokens(
    name: str, text: str, native: Loader
) -> None:
    assert native_tokens(native, name)(text) == python_tokens(text)


@pytest.mark.parametrize("name", TOKENIZER_MODULES)
@given(text=st.text(alphabet="ab_9+#中文 \n\u3400é😀\ud800", max_size=60))
def test_token_shaped_text_gives_the_python_tokens(
    name: str, text: str, native: Loader
) -> None:
    assert native_tokens(native, name)(text) == python_tokens(text)


@pytest.mark.parametrize("name", ANALYZERS)
def test_the_analyzers_match_the_mixed_one(name: str, native: Loader) -> None:
    native(name)
    text = "Rust 所有权 and C++ ﬁnal 中"
    mixed_native = build_pipeline([ANALYZERS[name], "nfkc", "stopwords"])
    python = build_pipeline(["mixed", "nfkc", "stopwords"])
    assert list(mixed_native.analyze(text)) == list(python.analyze(text))


@pytest.mark.parametrize("name", COUNTER_MODULES)
@pytest.mark.parametrize("text", EDGE_TEXTS)
def test_count_cjk_matches_a_regex(
    name: str, text: str, native: Loader
) -> None:
    module = native(name)
    expected = sum(map(len, re.findall(f"[{CJK}]+", text)))
    assert module.count_cjk(text) == expected


def test_capi_count_cjk_rejects_other_types(native: Loader) -> None:
    capi = native("sift.ext._capi")
    for bad in (b"abc", 3, None, ["中"]):
        with pytest.raises(TypeError, match="must be str"):
            capi.count_cjk(bad)
    with pytest.raises(TypeError):
        capi.count_cjk()


def test_cython_counts_utf8_in_any_buffer(native: Loader) -> None:
    cytok = native("sift.ext._cytok")
    text = "a中文b\u3400"
    data = text.encode("utf-8")
    assert cytok.count_cjk_utf8(data) == 3
    assert cytok.count_cjk_utf8(bytearray(data)) == 3
    assert cytok.count_cjk_utf8(memoryview(data)[1:]) == 3
    assert cytok.count_cjk_utf8(b"\xe4\xb8") == 0


@pytest.fixture(scope="module")
def ctok(native: Loader) -> ModuleType:
    """Return the ctypes module of the C tokenizer."""
    return native("sift.ext.ctok")


@pytest.fixture(scope="module")
def library(ctok: ModuleType) -> ctypes.CDLL:
    """Return libsifttok as ctypes loaded it."""
    return ctok._lib


def call(
    ctok: ModuleType, data: bytes, cap: int
) -> tuple[int, int, list[tuple[int, int]]]:
    """Call sift_tokenize with cap spans; return rc, n_out, spans."""
    lib = ctok._lib
    buf = (ctok.Span * (cap + 1))()
    # The span after the cap must stay as the canary.
    buf[cap].start = buf[cap].end = 12345
    n = ctypes.c_size_t(99)
    rc = lib.sift_tokenize(data, len(data), buf, cap, ctypes.byref(n))
    assert (buf[cap].start, buf[cap].end) == (12345, 12345)
    got = [(buf[i].start, buf[i].end) for i in range(min(cap, n.value))]
    return rc, n.value, got


def test_capacity_too_small_reports_the_full_count(ctok: ModuleType) -> None:
    data = "ab cd ef 中文字".encode()
    rc, n, got = call(ctok, data, 10)
    assert (rc, n) == (0, 5)
    assert got == [(0, 2), (3, 5), (6, 8), (9, 15), (12, 18)]
    for cap in range(5):
        rc, n, short = call(ctok, data, cap)
        assert (rc, n) == (-errno.ENOSPC, 5)
        assert short == got[:cap]


def test_no_room_at_all_counts_without_a_buffer(
    library: ctypes.CDLL,
) -> None:
    data = b"ab cd"
    n = ctypes.c_size_t()
    rc = library.sift_tokenize(data, len(data), None, 0, ctypes.byref(n))
    assert (rc, n.value) == (-errno.ENOSPC, 2)
    rc = library.sift_tokenize(b"", 0, None, 0, ctypes.byref(n))
    assert (rc, n.value) == (0, 0)


def test_bad_arguments_are_einval(
    library: ctypes.CDLL, ctok: ModuleType
) -> None:
    buf = (ctok.Span * 1)()
    n = ctypes.c_size_t(7)
    assert library.sift_tokenize(b"a", 1, buf, 1, None) == -errno.EINVAL
    assert (
        library.sift_tokenize(None, 1, buf, 1, ctypes.byref(n))
        == -errno.EINVAL
    )
    assert n.value == 0
    assert (
        library.sift_tokenize(b"a", 1, None, 1, ctypes.byref(n))
        == -errno.EINVAL
    )
    assert library.sift_tokenize(None, 0, None, 0, ctypes.byref(n)) == 0
    assert library.sift_count_cjk(None, 5) == 0


@given(data=st.binary(max_size=200))
def test_arbitrary_bytes_give_whole_valid_tokens(
    data: bytes, native: Loader
) -> None:
    ctok = native("sift.ext.ctok")
    flat = ctok.spans(data)
    last = -1
    for start, end in zip(flat[::2], flat[1::2], strict=True):
        assert 0 <= start < end <= len(data)
        assert start >= last
        last = start
        text = data[start:end].decode("utf-8")
        assert re.fullmatch(
            rf"[0-9a-z_]+(?:\+{{1,2}}|#)?|[{CJK}]{{1,2}}", text
        )


def test_invalid_utf8_is_skipped(native: Loader) -> None:
    ctok = native("sift.ext.ctok")
    data = b"ab\xe4\xb8 cd \xff\xfe e\xe4\xb8\xad\xe4\xb8 f \xed\xa0\x80g"
    spans = ctok.spans(data)
    words = [
        data[s:e].decode()
        for s, e in zip(spans[::2], spans[1::2], strict=True)
    ]
    assert words == ["ab", "cd", "e", "中", "f", "g"]


@pytest.fixture(scope="module")
def rs(native: Loader) -> ModuleType:
    """Return the Python wrapper of the Rust tokenizer."""
    return native("sift.ext.rs")


@pytest.mark.parametrize("threads", [0, 1, 2, 7])
def test_rust_many_gives_the_python_tokens_in_order(
    rs: ModuleType, threads: int
) -> None:
    texts = [
        *EDGE_TEXTS[:-1],
        *(p.read_text("utf-8") for p in sorted(MINI.glob("*.md"))),
    ]
    got = rs.tokens_many([fold(text) for text in texts], threads)
    assert got == [python_tokens(text) for text in texts]


@pytest.mark.slow
@pytest.mark.skipif(not CORPUS.is_dir(), reason="run `make corpus` first")
def test_rust_many_gives_the_python_tokens_of_the_corpus(
    rs: ModuleType,
) -> None:
    texts = [p.read_text("utf-8") for p in sorted(CORPUS.glob("*.md"))]
    got = rs.tokens_many([fold(text) for text in texts])
    assert got == [python_tokens(text) for text in texts]


@given(
    texts=st.lists(
        st.text(alphabet="ab_9+#中文 \n\u3400é😀\ud800", max_size=40),
        max_size=12,
    ),
    threads=st.integers(0, 5),
)
def test_rust_many_is_many_times_one(
    texts: list[str], threads: int, native: Loader
) -> None:
    rs = native("sift.ext.rs")
    folded = [fold(text) for text in texts]
    assert rs.tokens_many(folded, threads) == [rs.tokens(t) for t in folded]


def test_rust_many_of_nothing_is_empty(rs: ModuleType) -> None:
    assert rs.tokens_many([]) == []
    assert rs.tokens_many([""]) == [[]]


def test_rust_too_many_threads_is_a_value_error(rs: ModuleType) -> None:
    with pytest.raises(ValueError, match="between 0 and 256, got 257"):
        rs.tokens_many(["a"], 257)
    assert rs.tokens_many(["a"], 256) == [[Token("a", 0, 0, 1)]]


def test_rust_raw_functions_refuse_surrogates(native: Loader) -> None:
    raw = native("sift._rs")
    with pytest.raises(UnicodeEncodeError):
        raw.tokenize("a\ud800b")
    with pytest.raises(UnicodeEncodeError):
        raw.tokenize_many(["a", "b\udfff"])
    assert raw.tokenize("a中文") == [("a", 0, 0, 1), ("中文", 1, 1, 3)]


def test_rust_wrong_types_are_type_errors(native: Loader) -> None:
    raw = native("sift._rs")
    for bad in (b"abc", 3, None):
        with pytest.raises(TypeError):
            raw.tokenize(bad)
    with pytest.raises(TypeError):
        raw.tokenize_many("abc")
    with pytest.raises(OverflowError):
        raw.tokenize_many(["a"], -1)


def test_rust_panic_is_a_base_exception(native: Loader) -> None:
    raw = native("sift._rs")
    if not hasattr(raw, "panic_for_lab"):
        pytest.skip("panic_for_lab exists in debug builds only")
    with pytest.raises(BaseException, match="boom") as info:
        raw.panic_for_lab("boom")
    assert type(info.value).__name__ == "PanicException"
    assert not isinstance(info.value, Exception)

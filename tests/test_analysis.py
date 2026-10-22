"""Tests for sift.analysis: tokenizers, filters and the pipeline."""

import pytest

from sift.analysis import (
    REGISTRY,
    Analyzer,
    CjkBigramTokenizer,
    LatinTokenizer,
    MixedTokenizer,
    NfkcCasefold,
    Pipeline,
    StopwordFilter,
    Token,
    build_pipeline,
    iter_tokens,
    tokenize,
)
from sift.analysis.filters import TokenFilterBase
from sift.analysis.tokenize import fold
from sift.errors import ConfigError


@pytest.mark.parametrize(
    ("text", "terms"),
    [
        ("Hello, World!", ["hello", "world"]),
        ("snake_case 42", ["snake_case", "42"]),
        ("C++ and C# and c++20", ["c++", "and", "c#", "and", "c++", "20"]),
        ("全文搜索", ["全文", "文搜", "搜索"]),
        ("索", ["索"]),
        ("a索b", ["a", "索", "b"]),
        ("ﬁne ＡＢＣ", ["fine", "abc"]),
        ("", []),
        ("... --- !!!", []),
    ],
)
def test_tokenize(text: str, terms: list[str]) -> None:
    assert tokenize(text) == terms


def test_accented_letters_split_a_word() -> None:
    # Latin runs are [0-9a-z_]: "é" is not in the class. This pins the
    # current behavior; changing it is a decision, not a fix.
    assert tokenize("café") == ["caf"]
    assert tokenize("naïve") == ["na", "ve"]


def test_token_fields() -> None:
    tokens = list(iter_tokens("ab 搜索引"))
    assert tokens == [
        Token("ab", 0, 0, 2),
        Token("搜索", 1, 3, 5),
        Token("索引", 2, 4, 6),
    ]


def test_offsets_are_into_the_folded_text() -> None:
    text = "ﬁne"  # one ligature character, "fine" after NFKC
    (token,) = iter_tokens(text)
    assert (token.start, token.end) == (0, 4)
    assert fold(text)[token.start : token.end] == token.text
    assert len(text) == 3


def test_iter_tokens_is_lazy() -> None:
    stream = iter_tokens("one two three")
    assert next(stream).text == "one"


def test_latin_tokenizer_ignores_cjk_and_keeps_case() -> None:
    tokens = LatinTokenizer().analyze("Rust 所有权 C++")
    assert [t.text for t in tokens] == ["Rust", "C++"]


def test_cjk_tokenizer_ignores_latin() -> None:
    terms = [t.text for t in CjkBigramTokenizer().analyze("ab 所有权 c 与")]
    assert terms == ["所有", "有权", "与"]


def test_mixed_tokenizer_is_iter_tokens() -> None:
    text = "Rust 所有权 ﬁ"
    assert list(MixedTokenizer().analyze(text)) == list(iter_tokens(text))


def test_registry_names() -> None:
    assert {"latin", "cjk-bigram", "mixed"} <= set(REGISTRY)


def test_duplicate_analyzer_name_is_refused() -> None:
    with pytest.raises(ValueError, match="analyzer name taken: 'latin'"):

        class Again(Analyzer, name="latin"):  # pragma: no cover
            def analyze(self, text):
                yield from ()


def test_analyzer_is_abstract() -> None:
    with pytest.raises(TypeError, match="abstract"):
        Analyzer()  # type: ignore[abstract]


def test_nfkc_filter_folds_token_text() -> None:
    stream = [Token("ＡＢ", 0, 0, 2), Token("ok", 1, 3, 5)]
    out = list(NfkcCasefold()(stream))
    assert [t.text for t in out] == ["ab", "ok"]
    assert out[1] is stream[1]


def test_stopword_filter_keeps_positions() -> None:
    pipeline = Pipeline(MixedTokenizer(), StopwordFilter())
    tokens = list(pipeline.analyze("the cat of dogs"))
    assert [(t.text, t.position) for t in tokens] == [("cat", 1), ("dogs", 3)]


def test_default_pipeline() -> None:
    pipeline = build_pipeline()
    assert repr(pipeline) == "Pipeline(MixedTokenizer, NfkcCasefold)"
    assert pipeline.terms("Ünï 搜索") == ["n", "搜索"]


def test_build_pipeline_with_a_filter() -> None:
    pipeline = build_pipeline(["latin", "nfkc", "stopwords"])
    assert pipeline.terms("The CAT") == ["cat"]


@pytest.mark.parametrize(
    ("names", "message"),
    [
        ([], "needs a tokenizer"),
        (["nope"], "unknown tokenizer 'nope'"),
        (["mixed", "nope"], "unknown filter 'nope'"),
        (["nfkc"], "unknown tokenizer 'nfkc'"),
        (["mixed", "latin"], "unknown filter 'latin'"),
    ],
)
def test_build_pipeline_errors(names: list[str], message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        build_pipeline(names)


def test_duplicate_filter_name_is_refused() -> None:
    with pytest.raises(ValueError, match="filter name taken: 'nfkc'"):

        class Again(TokenFilterBase, name="nfkc"):
            pass


def test_filter_base_class_is_not_callable_work() -> None:
    with pytest.raises(NotImplementedError):
        TokenFilterBase()(iter(()))

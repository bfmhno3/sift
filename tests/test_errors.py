"""Tests for sift.errors."""

from pathlib import Path

import pytest

from sift.errors import (
    ConfigError,
    FrontMatterError,
    IndexCorruptError,
    IndexMissingError,
    QuerySyntaxError,
    SiftError,
)


@pytest.mark.parametrize(
    "cls",
    [
        QuerySyntaxError,
        FrontMatterError,
        ConfigError,
        IndexMissingError,
        IndexCorruptError,
    ],
)
def test_every_error_is_a_sift_error(cls: type[Exception]) -> None:
    assert issubclass(cls, SiftError)
    assert not issubclass(SiftError, (KeyError, ValueError))


def test_query_syntax_error_attributes_and_str() -> None:
    error = QuerySyntaxError("bad", "a )", 2)
    assert (error.message, error.query, error.position) == ("bad", "a )", 2)
    assert str(error) == "bad"
    assert error.args == ("bad", "a )", 2)


def test_render_puts_the_caret_under_the_position() -> None:
    error = QuerySyntaxError("unexpected ')'", "a )", 2)
    assert error.render() == "unexpected ')'\n  a )\n    ^"


def test_render_counts_wide_characters_twice() -> None:
    error = QuerySyntaxError("bad", "搜索 )", 3)
    caret = error.render().splitlines()[-1]
    assert caret == "  " + " " * 5 + "^"


def test_render_ignores_combining_marks() -> None:
    error = QuerySyntaxError("bad", "e\u0301 )", 3)
    assert error.render().splitlines()[-1] == "  " + " " * 2 + "^"


def test_front_matter_error_str_with_and_without_a_path() -> None:
    assert str(FrontMatterError(Path("a.md"), 4, "oops")) == "a.md:4: oops"
    assert str(FrontMatterError(None, 4, "oops")) == "line 4: oops"


def test_catching_sift_error_catches_the_family_only() -> None:
    with pytest.raises(SiftError):
        raise ConfigError("x")
    with pytest.raises(KeyError):
        try:
            {}["missing"]
        except SiftError:  # pragma: no cover
            pytest.fail("a KeyError is not a SiftError")

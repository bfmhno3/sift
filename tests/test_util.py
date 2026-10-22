"""Tests for sift.util."""

import pytest

from sift.util import compose, timed


def test_compose_applies_left_to_right() -> None:
    add_one = compose(lambda x: x + 1, lambda x: x * 10)
    assert add_one(2) == 30


def test_compose_of_nothing_is_the_identity() -> None:
    assert compose()("same") == "same"


def test_timed_reports_to_stderr_and_returns(
    capsys: pytest.CaptureFixture[str],
) -> None:
    @timed
    def double(x: int) -> int:
        """Return twice x."""
        return 2 * x

    assert double(4) == 8
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("test_timed_reports_to_stderr_and_returns")
    assert "double took " in captured.err
    assert double.__doc__ == "Return twice x."


def test_timed_reports_even_when_the_function_raises(
    capsys: pytest.CaptureFixture[str],
) -> None:
    @timed
    def fail() -> None:
        raise KeyError("x")

    with pytest.raises(KeyError):
        fail()
    assert "fail took " in capsys.readouterr().err

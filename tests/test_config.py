"""Tests for sift.config."""

from pathlib import Path

import pytest

from sift.config import Config, load_config
from sift.errors import ConfigError

REPO = Path(__file__).parent.parent


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "sift.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_shipped_sift_toml_is_the_default() -> None:
    assert load_config(REPO / "sift.toml") == Config()


def test_every_setting(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
[index]
corpus = "posts"
path = "idx"

[analysis]
pipeline = ["latin"]

[search]
k1 = 2
b = 0.5
limit = 3
""",
    )
    assert load_config(path) == Config(
        corpus=Path("posts"),
        index_path=Path("idx"),
        pipeline=("latin",),
        k1=2.0,
        b=0.5,
        limit=3,
    )


def test_missing_keys_keep_the_defaults(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, "[search]\nlimit = 5\n"))
    assert config == Config(limit=5)


def test_none_without_a_file_gives_the_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert load_config(None) == Config()


def test_none_reads_sift_toml_in_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(tmp_path, "[search]\nlimit = 7\n")
    monkeypatch.chdir(tmp_path)
    assert load_config().limit == 7


def test_explicit_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="no config file"):
        load_config(tmp_path / "nope.toml")


def test_toml_syntax_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"sift\.toml"):
        load_config(write(tmp_path, "[index\n"))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[nope]\n", "unknown section"),
        ("[index]\ncorpuss = 'x'\n", "unknown key in .index."),
        ("[index]\ncorpus = 3\n", "must be a string"),
        ("index = 1\n", "must be a table"),
        ("[analysis]\npipeline = []\n", "non-empty list"),
        ("[analysis]\npipeline = 'mixed'\n", "non-empty list"),
        ("[analysis]\npipeline = [1]\n", "non-empty list"),
        ("[search]\nk1 = 'x'\n", "must be a number"),
        ("[search]\nk1 = true\n", "must be a number"),
        ("[search]\nk1 = -1\n", "must not be negative"),
        ("[search]\nb = 1.5\n", "between 0 and 1"),
        ("[search]\nlimit = 0\n", "at least 1"),
        ("[search]\nlimit = 2.5\n", "at least 1"),
    ],
)
def test_invalid_settings(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, text))

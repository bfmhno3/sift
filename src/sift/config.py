"""Settings from ``sift.toml``.

The file is read with ``tomllib``, which only reads: TOML has no
standard way to write a file back without losing comments, so Sift
never edits its own configuration.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sift.errors import ConfigError

DEFAULT_PATH = Path("sift.toml")


@dataclass(frozen=True, slots=True)
class Config:
    """The settings of Sift; the defaults match the shipped sift.toml."""

    corpus: Path = Path("corpus/posts")
    index_path: Path = Path(".sift")
    pipeline: tuple[str, ...] = ("mixed", "nfkc", "stopwords")
    k1: float = 1.2
    b: float = 0.75
    limit: int = 10


def _section(
    path: Path, data: dict[str, Any], name: str, keys: set[str]
) -> dict[str, Any]:
    """Return data[name] after checking that it only has known keys."""
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"{path}: [{name}] must be a table")
    unknown = sorted(set(section) - keys)
    if unknown:
        raise ConfigError(
            f"{path}: unknown key in [{name}]: {', '.join(unknown)}"
        )
    return section


def _number(
    path: Path, section: dict[str, Any], name: str, key: str
) -> float | None:
    """Return a float setting (an int is fine), or None if absent."""
    if key not in section:
        return None
    value = section[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"{path}: [{name}] {key} must be a number")
    return float(value)


def load_config(path: Path | None = None) -> Config:
    """Read the settings from path, or from ./sift.toml if path is None.

    A missing ./sift.toml gives the defaults; a missing explicit path
    does not. Unknown sections or keys, wrong types and TOML syntax
    errors raise ConfigError. Relative paths stay relative to the
    current directory.
    """
    if path is None:
        if not DEFAULT_PATH.is_file():
            return Config()
        path = DEFAULT_PATH
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError:
        raise ConfigError(f"no config file at {path}") from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: {error}") from None
    unknown = sorted(set(data) - {"index", "analysis", "search"})
    if unknown:
        raise ConfigError(f"{path}: unknown section: {', '.join(unknown)}")
    default = Config()
    index = _section(path, data, "index", {"corpus", "path"})
    analysis = _section(path, data, "analysis", {"pipeline"})
    search = _section(path, data, "search", {"k1", "b", "limit"})
    for key in ("corpus", "path"):
        if key in index and not isinstance(index[key], str):
            raise ConfigError(f"{path}: [index] {key} must be a string")
    names = analysis.get("pipeline", list(default.pipeline))
    if (
        not isinstance(names, list)
        or not names
        or not all(isinstance(name, str) for name in names)
    ):
        raise ConfigError(
            f"{path}: [analysis] pipeline must be a non-empty list"
        )
    k1 = _number(path, search, "search", "k1")
    b = _number(path, search, "search", "b")
    limit = search.get("limit", default.limit)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ConfigError(
            f"{path}: [search] limit must be an integer of at least 1"
        )
    if k1 is not None and k1 < 0:
        raise ConfigError(f"{path}: [search] k1 must not be negative")
    if b is not None and not 0 <= b <= 1:
        raise ConfigError(f"{path}: [search] b must be between 0 and 1")
    return Config(
        corpus=Path(index.get("corpus", default.corpus)),
        index_path=Path(index.get("path", default.index_path)),
        pipeline=tuple(names),
        k1=default.k1 if k1 is None else k1,
        b=default.b if b is None else b,
        limit=limit,
    )

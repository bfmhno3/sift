"""Settings from ``sift.toml``, declared with descriptors.

The file is read with ``tomllib``, which only reads: TOML has no
standard way to write a file back without losing comments, so Sift
never edits its own configuration.

A setting is a descriptor on the class: ``limit = Setting(int,
default=10, min=1, max=100, section="search")``. Reading
``config.limit`` returns the stored value or the default; assigning
checks the type and the range, so a bad value fails where it is
written, not where it is used.
"""

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar, Self, cast, overload

from sift.errors import ConfigError

DEFAULT_PATH = Path("sift.toml")

_NOUNS: dict[type, str] = {
    int: "an integer",
    float: "a number",
    str: "a string",
}


class SettingBase:
    """What ``Settings`` needs from a descriptor, whatever its type.

    ``name`` is the attribute name, filled by ``__set_name__``.
    ``section`` and ``key`` say where the value lives in the TOML
    file; ``key`` defaults to the attribute name.
    """

    def __init__(self, *, section: str, key: str | None = None) -> None:
        """Keep the TOML location; the name arrives later."""
        self.name = ""
        self.section = section
        self.key = key or ""
        self._explicit_key = key
        self.default: object = None

    def __set_name__(self, owner: type, name: str) -> None:
        """Record the attribute name the class body gave this object."""
        self.name = name
        self.key = self._explicit_key or name

    @property
    def label(self) -> str:
        """Return ``[section] key``, the way messages name a setting."""
        return f"[{self.section}] {self.key}"

    def parse(self, raw: object) -> object:
        """Return the value for a raw TOML value, or raise ConfigError."""
        raise NotImplementedError


class Setting[T](SettingBase):
    """A typed, validated attribute of a ``Settings`` class.

    kind is the required type (``bool`` is never an ``int``; an
    ``int`` is fine for a ``float`` and is stored as a float). min and
    max bound int and float settings, both inclusive. The default is
    checked when the class is created.
    """

    def __init__(
        self,
        kind: type[T],
        *,
        default: T,
        section: str,
        key: str | None = None,
        min: float | None = None,
        max: float | None = None,
    ) -> None:
        """Keep the rules; min and max need an int or float kind."""
        super().__init__(section=section, key=key)
        if (min is not None or max is not None) and kind not in (int, float):
            raise TypeError("min and max need an int or float setting")
        self.kind = kind
        self.default = default
        self.min = min
        self.max = max

    def __set_name__(self, owner: type, name: str) -> None:
        """Record the name, then check that the default is valid."""
        super().__set_name__(owner, name)
        try:
            self.validate(self.default)
        except ConfigError as error:
            raise ValueError(f"bad default: {error}") from None

    @overload
    def __get__(self, instance: None, owner: type[object]) -> Self: ...
    @overload
    def __get__(self, instance: object, owner: type[object]) -> T: ...
    def __get__(
        self, instance: object | None, owner: type[object]
    ) -> Self | T:
        """Return the stored value; on the class, the setting itself."""
        if instance is None:
            return self
        stored = instance.__dict__.get(self.name, self.default)
        return cast("T", stored)

    def __set__(self, instance: object, value: T) -> None:
        """Validate value and store it in the instance."""
        instance.__dict__[self.name] = self.validate(value)

    def _noun(self) -> str:
        """Return how a message names the kind: "an integer"."""
        return _NOUNS.get(self.kind, f"a {self.kind.__name__}")

    def _out_of_range(self) -> ConfigError:
        """Return the error for a number outside min and max."""
        low, high = self.min, self.max
        if low is not None and high is not None:
            rule = f"{self._noun()} between {low:g} and {high:g}"
        elif low == 0:
            return ConfigError(f"{self.label} must not be negative")
        elif low is not None:
            rule = f"{self._noun()} of at least {low:g}"
        else:
            rule = f"{self._noun()} of at most {high:g}"
        return ConfigError(f"{self.label} must be {rule}")

    def validate(self, value: object) -> T:
        """Return value if it has the right type and range.

        Raise ConfigError otherwise.
        """
        if isinstance(value, bool) and self.kind is not bool:
            raise ConfigError(f"{self.label} must be {self._noun()}")
        if self.kind is float and isinstance(value, int):
            value = float(value)
        if not isinstance(value, self.kind):
            raise ConfigError(f"{self.label} must be {self._noun()}")
        if isinstance(value, int | float):
            below = self.min is not None and value < self.min
            above = self.max is not None and value > self.max
            if below or above:
                raise self._out_of_range()
        checked: object = value
        return cast("T", checked)

    def parse(self, raw: object) -> T:
        """Return the setting for a TOML value (same as validate)."""
        return self.validate(raw)


class PathSetting(Setting[Path]):
    """A Path setting; TOML holds it as a string."""

    def __init__(
        self,
        *,
        default: Path,
        section: str,
        key: str | None = None,
    ) -> None:
        """Keep the default and the TOML location."""
        super().__init__(Path, default=default, section=section, key=key)

    def parse(self, raw: object) -> Path:
        """Turn a TOML string into a Path."""
        if not isinstance(raw, str):
            raise ConfigError(f"{self.label} must be a string")
        return self.validate(Path(raw))


class StrTupleSetting(Setting[tuple[str, ...]]):
    """A non-empty tuple of strings; TOML holds it as a list."""

    def __init__(
        self,
        *,
        default: tuple[str, ...],
        section: str,
        key: str | None = None,
    ) -> None:
        """Keep the default and the TOML location."""
        super().__init__(tuple, default=default, section=section, key=key)

    def validate(self, value: object) -> tuple[str, ...]:
        """Return value if it is a non-empty tuple of strings."""
        if isinstance(value, tuple):
            items = cast("tuple[object, ...]", value)
            if items and all(isinstance(item, str) for item in items):
                return cast("tuple[str, ...]", items)
        raise ConfigError(f"{self.label} must be a non-empty list")

    def parse(self, raw: object) -> tuple[str, ...]:
        """Turn a TOML list of strings into a tuple."""
        if not isinstance(raw, list):
            raise ConfigError(f"{self.label} must be a non-empty list")
        return self.validate(tuple(cast("list[object]", raw)))


def _table(
    path: Path, data: Mapping[str, object], name: str, keys: set[str]
) -> Mapping[str, object]:
    """Return data[name] after checking that it only has known keys."""
    found = data.get(name, {})
    if not isinstance(found, Mapping):
        raise ConfigError(f"{path}: [{name}] must be a table")
    table = cast("Mapping[str, object]", found)
    unknown = sorted(set(table) - keys)
    if unknown:
        raise ConfigError(
            f"{path}: unknown key in [{name}]: {', '.join(unknown)}"
        )
    return table


class Settings:
    """Base class of a group of settings.

    ``__init_subclass__`` runs once per subclass, after the class
    body: it gathers the ``SettingBase`` descriptors of the class and
    of its bases into ``_settings``, in declaration order, so the
    constructor, ``==`` and ``from_toml`` need no list of names.
    """

    _settings: ClassVar[dict[str, SettingBase]] = {}

    def __init_subclass__(cls) -> None:
        """Collect the settings of cls and of its bases."""
        super().__init_subclass__()
        found: dict[str, SettingBase] = {}
        for base in reversed(cls.__mro__):
            for name, value in vars(base).items():
                if isinstance(value, SettingBase):
                    found[name] = value
        cls._settings = found

    def __init__(self, **values: object) -> None:
        """Set the given settings; the others keep their defaults."""
        unknown = sorted(set(values) - set(self._settings))
        if unknown:
            raise TypeError(f"unknown setting: {', '.join(unknown)}")
        for name, value in values.items():
            setattr(self, name, value)

    def values(self) -> dict[str, object]:
        """Return every setting by name, defaults included."""
        return {name: getattr(self, name) for name in self._settings}

    def __eq__(self, other: object) -> bool:
        """Compare the values of two settings objects of one class."""
        if type(other) is not type(self):
            return NotImplemented
        return self.values() == other.values()

    def __repr__(self) -> str:
        """Return ``Config(limit=10, ...)``."""
        pairs = ", ".join(f"{k}={v!r}" for k, v in self.values().items())
        return f"{type(self).__name__}({pairs})"

    @classmethod
    def from_toml(cls, data: Mapping[str, object], path: Path) -> Self:
        """Build an instance from parsed TOML; path is for messages.

        Unknown sections or keys, wrong types and out-of-range values
        raise ConfigError naming path.
        """
        sections: dict[str, set[str]] = {}
        for setting in cls._settings.values():
            sections.setdefault(setting.section, set()).add(setting.key)
        unknown = sorted(set(data) - set(sections))
        if unknown:
            raise ConfigError(f"{path}: unknown section: {', '.join(unknown)}")
        values: dict[str, object] = {}
        for section, keys in sections.items():
            table = _table(path, data, section, keys)
            for name, setting in cls._settings.items():
                if setting.section != section or setting.key not in table:
                    continue
                try:
                    values[name] = setting.parse(table[setting.key])
                except ConfigError as error:
                    raise ConfigError(f"{path}: {error}") from None
        return cls(**values)


class Config(Settings):
    """The settings of Sift; the defaults match the shipped sift.toml."""

    corpus = PathSetting(default=Path("corpus/posts"), section="index")
    index_path = PathSetting(
        default=Path(".sift"), section="index", key="path"
    )
    pipeline = StrTupleSetting(
        default=("mixed", "nfkc", "stopwords"), section="analysis"
    )
    k1 = Setting(float, default=1.2, min=0.0, section="search")
    b = Setting(float, default=0.75, min=0.0, max=1.0, section="search")
    limit = Setting(int, default=10, min=1, max=100, section="search")


def load_config(path: Path | None = None) -> Config:
    """Read the settings from path, or from ./sift.toml if path is None.

    A missing ./sift.toml gives the defaults; a missing explicit path
    does not. Unknown sections or keys, wrong types, values out of
    range and TOML syntax errors raise ConfigError. Relative paths
    stay relative to the current directory.
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
    return Config.from_toml(data, path)

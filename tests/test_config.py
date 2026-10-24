"""Tests for sift.config."""

from pathlib import Path

import pytest

from sift.config import (
    Config,
    PathSetting,
    Setting,
    Settings,
    StrTupleSetting,
    load_config,
)
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
        ("[search]\nlimit = 0\n", "integer between 1 and 100"),
        ("[search]\nlimit = 2.5\n", "must be an integer"),
        ("[search]\nlimit = 101\n", "integer between 1 and 100"),
    ],
)
def test_invalid_settings(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, text))


def test_errors_name_the_file(tmp_path: Path) -> None:
    path = write(tmp_path, "[search]\nlimt = 3\n")
    with pytest.raises(ConfigError, match=r"sift\.toml: unknown key"):
        load_config(path)
    path = write(tmp_path, "[search]\nlimit = 0\n")
    with pytest.raises(ConfigError, match=r"sift\.toml: \[search\] limit"):
        load_config(path)


class Demo(Settings):
    """A tiny settings class for the descriptor tests."""

    ratio = Setting(float, default=0.5, min=0.0, max=1.0, section="s")
    count = Setting(int, default=3, min=1, section="s", key="n")
    name = Setting(str, default="x", section="t")


class Child(Demo):
    """Adds one setting and overrides another."""

    count = Setting(int, default=7, min=5, section="s", key="n")
    extra = Setting(bool, default=False, section="t")


def test_set_name_records_the_attribute_name() -> None:
    assert Demo.ratio.name == "ratio"
    assert Demo.count.name == "count"
    assert Demo.count.key == "n"
    assert Demo.ratio.key == "ratio"
    assert Demo.count.label == "[s] n"


def test_class_access_returns_the_descriptor() -> None:
    assert isinstance(Demo.ratio, Setting)
    assert Demo.ratio.default == 0.5


def test_instance_access_returns_default_then_value() -> None:
    demo = Demo()
    assert demo.count == 3
    assert "count" not in vars(demo)
    demo.count = 9
    assert demo.count == 9
    assert vars(demo) == {"count": 9}


def test_int_is_stored_as_float() -> None:
    demo = Demo(ratio=1)
    assert demo.ratio == 1.0
    assert isinstance(demo.ratio, float)


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("count", "3", r"\[s\] n must be an integer"),
        ("count", 2.0, "must be an integer"),
        ("count", True, "must be an integer"),
        ("ratio", "0.5", "must be a number"),
        ("ratio", False, "must be a number"),
        ("name", 1, "must be a string"),
        ("count", 0, "integer of at least 1"),
        ("ratio", -0.1, "between 0 and 1"),
        ("ratio", 1.1, "between 0 and 1"),
    ],
)
def test_set_validates(name: str, value: object, message: str) -> None:
    demo = Demo()
    with pytest.raises(ConfigError, match=message):
        setattr(demo, name, value)
    assert getattr(demo, name) == Demo._settings[name].default


def test_bounds_are_inclusive() -> None:
    demo = Demo(ratio=0.0, count=1)
    demo.ratio = 1.0
    assert (demo.ratio, demo.count) == (1.0, 1)


def test_min_without_max_and_max_without_min() -> None:
    class One(Settings):
        low = Setting(int, default=5, min=5, section="s")
        high = Setting(int, default=5, max=5, section="s")

    with pytest.raises(ConfigError, match="of at least 5"):
        One(low=4)
    with pytest.raises(ConfigError, match="of at most 5"):
        One(high=6)


def test_bad_default_fails_at_class_creation() -> None:
    with pytest.raises(ValueError, match="bad default"):

        class Bad(Settings):
            limit = Setting(int, default=0, min=1, section="s")

    with pytest.raises(TypeError, match="min and max"):
        Setting(str, default="x", min=1, section="s")


def test_init_subclass_collects_in_declaration_order() -> None:
    assert list(Demo._settings) == ["ratio", "count", "name"]
    assert list(Config._settings) == [
        "corpus",
        "index_path",
        "pipeline",
        "k1",
        "b",
        "limit",
    ]
    assert Settings._settings == {}


def test_inheritance_collects_and_overrides() -> None:
    assert list(Child._settings) == ["ratio", "count", "name", "extra"]
    assert Child._settings["count"] is Child.count
    assert Child._settings["count"] is not Demo._settings["count"]
    assert Child().count == 7
    assert Demo().count == 3
    with pytest.raises(ConfigError, match="at least 5"):
        Child(count=4)
    assert Child(ratio=0.25, extra=True).values() == {
        "ratio": 0.25,
        "count": 7,
        "name": "x",
        "extra": True,
    }


def test_unknown_setting_in_the_constructor() -> None:
    with pytest.raises(ConfigError, match="unknown setting: nope"):
        Demo(nope=1)
    with pytest.raises(ConfigError, match=r"did you mean count\?"):
        Demo(cuont=1)


def test_assigning_an_unknown_attribute_is_refused() -> None:
    config = Config()
    with pytest.raises(ConfigError, match=r"did you mean limit\?"):
        config.limt = 5  # type: ignore[attr-defined]
    assert "limt" not in vars(config)


def test_delete_resets_to_the_default() -> None:
    demo = Demo(count=9)
    del demo.count
    assert demo.count == 3
    assert "count" not in vars(demo)
    del demo.count  # deleting twice is fine


def test_bool_and_int_rules_survive_the_fast_path() -> None:
    assert Demo(ratio=1).ratio == 1.0
    assert isinstance(Demo(ratio=1).ratio, float)
    with pytest.raises(ConfigError):
        Demo(count=True)
    with pytest.raises(ConfigError):
        Demo(ratio=True)


def test_eq_and_repr() -> None:
    assert Demo(count=4) == Demo(count=4)
    assert Demo(count=4) != Demo(count=5)
    assert Demo() != Child()
    assert Demo() == Demo(count=3)
    assert repr(Demo(count=4)) == "Demo(ratio=0.5, count=4, name='x')"


def test_from_toml_uses_the_toml_keys() -> None:
    data = {"s": {"n": 8, "ratio": 1}, "t": {"name": "y"}}
    demo = Demo.from_toml(data, Path("demo.toml"))
    assert demo.values() == {"ratio": 1.0, "count": 8, "name": "y"}


def test_from_toml_errors_name_the_path() -> None:
    path = Path("demo.toml")
    with pytest.raises(ConfigError, match=r"demo\.toml: \[s\] n must be"):
        Demo.from_toml({"s": {"n": 0}}, path)
    with pytest.raises(
        ConfigError, match=r"demo\.toml: unknown key in .s.: count"
    ):
        Demo.from_toml({"s": {"count": 1}}, path)
    with pytest.raises(ConfigError, match=r"demo\.toml: unknown section: u"):
        Demo.from_toml({"u": {}}, path)


def test_from_toml_on_a_subclass_returns_the_subclass() -> None:
    child = Child.from_toml({"t": {"extra": True}}, Path("c.toml"))
    assert isinstance(child, Child)
    assert child.extra is True


def test_path_and_tuple_settings() -> None:
    assert isinstance(Config.corpus, PathSetting)
    assert isinstance(Config.pipeline, StrTupleSetting)
    config = Config()
    config.corpus = Path("elsewhere")
    assert config.corpus == Path("elsewhere")
    with pytest.raises(ConfigError, match="must be a string"):
        Config.corpus.parse(3)
    with pytest.raises(ConfigError, match="non-empty list"):
        config.pipeline = ()
    with pytest.raises(ConfigError, match="non-empty list"):
        setattr(config, "pipeline", ("a", 1))  # noqa: B010
    config.pipeline = ("latin",)
    assert config.pipeline == ("latin",)


def test_assignment_after_construction_is_validated() -> None:
    config = Config()
    with pytest.raises(ConfigError, match="limit"):
        config.limit = 0
    assert config.limit == 10

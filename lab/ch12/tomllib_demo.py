"""tomllib: read sift.toml, and why the module cannot write."""

import tempfile
import tomllib
from pathlib import Path

from sift.config import load_config
from sift.errors import ConfigError

SAMPLE = """
title = "TOML types"
count = 3
ratio = 0.75
flag = true
when = 2026-01-02T08:00:00+08:00
day = 2026-01-02
tags = ["a", "b"]

[table]
key = "value"

[[points]]
x = 1

[[points]]
x = 2
"""


def main() -> None:
    """Parse the repository's sift.toml and a sample document."""
    with Path("sift.toml").open("rb") as file:
        data = tomllib.load(file)
    print("sift.toml as a dict:")
    for section, values in data.items():
        print(f"  [{section}]", values)
    print("types:", {k: type(v).__name__ for k, v in data["search"].items()})
    print("load_config:", load_config(Path("sift.toml")))

    print("--- loads() takes str, load() takes a binary file")
    parsed = tomllib.loads(SAMPLE)
    for key, value in parsed.items():
        print(f"  {key:<6} {type(value).__name__:<9} {value!r}")
    try:
        with Path("sift.toml").open(encoding="utf-8") as text_file:
            tomllib.load(text_file)  # type: ignore[arg-type]
    except TypeError as error:
        print("TypeError:", error)

    print("--- errors")
    try:
        tomllib.loads("a = 1\na = 2\n")
    except tomllib.TOMLDecodeError as error:
        print("TOMLDecodeError:", error)
    try:
        tomllib.loads("[search\nlimit = 3\n")
    except tomllib.TOMLDecodeError as error:
        print("TOMLDecodeError:", error)

    print("--- read only")
    print(
        "has dumps/dump:", hasattr(tomllib, "dumps"), hasattr(tomllib, "dump")
    )
    print("public names  :", sorted(n for n in dir(tomllib) if n[0] != "_"))
    print("a rewrite would drop comments and layout; edit the file by hand")

    print("--- load_config rejects what the file format allows")
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "sift.toml"
        bad.write_text("[search]\nlimt = 3\n", encoding="utf-8")
        print("tomllib accepts it:", tomllib.loads(bad.read_text()))
        try:
            load_config(bad)
        except ConfigError as error:
            print("ConfigError:", error.args[0].replace(tmp, "<tmp>"))
    try:
        load_config(Path("no-such.toml"))
    except ConfigError as error:
        print("ConfigError:", error)


if __name__ == "__main__":
    main()

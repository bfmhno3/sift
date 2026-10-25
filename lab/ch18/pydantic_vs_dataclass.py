"""Time the validation of one object: pydantic, descriptors, dataclass.

The three classes hold the same three settings (limit, k1, b) with the
rules of Config (chapter 15): limit in 1..100, k1 at least 0, b in 0..1.

* ``Config``: the descriptors of chapter 15, which check on every
  assignment, in Python.
* ``Model``: a pydantic v2 model; the checks run in pydantic-core
  (Rust) and the model is built in one call.
* ``Plain``: a dataclass with slots and no check at all.

Each cell is the best of 5 runs of N objects, in ns per object.
"""

import contextlib
import json
import timeit
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from sift.config import Config
from sift.errors import ConfigError

N = 100_000
REPEAT = 5


class Model(BaseModel):
    """The rules of Config as pydantic fields."""

    limit: int = Field(default=10, ge=1, le=100)
    k1: float = Field(default=1.2, ge=0.0)
    b: float = Field(default=0.75, ge=0.0, le=1.0)


@dataclass(slots=True)
class Plain:
    """The same fields, no rules."""

    limit: int = 10
    k1: float = 1.2
    b: float = 0.75


VALUES = {"limit": 25, "k1": 1.5, "b": 0.5}
TEXT = json.dumps(VALUES)
ADAPTER = TypeAdapter(Model)


def per_object(
    label: str, call: Callable[[], object], base: float | None
) -> float:
    """Time call() N times; print ns per object; return that number."""
    best = min(timeit.repeat(call, number=N, repeat=REPEAT)) / N * 1e9
    ratio = "" if base is None else f"  {best / base:5.1f}x plain"
    print(f"{label:<38} {best:8.0f} ns{ratio}")
    return best


def main() -> None:
    """Print the cost of building one object each way."""
    values = VALUES
    plain = per_object("dataclass(**dict)", lambda: Plain(**values), None)
    per_object(
        "Config(**dict)   (descriptors)", lambda: Config(**values), plain
    )
    per_object("Model(**dict)", lambda: Model(**values), plain)
    per_object(
        "Model.model_validate(dict)",
        lambda: Model.model_validate(values),
        plain,
    )
    per_object(
        "TypeAdapter(Model).validate_python",
        lambda: ADAPTER.validate_python(values),
        plain,
    )
    per_object(
        "Model.model_construct(**dict)  (no check)",
        lambda: Model.model_construct(**values),
        plain,
    )
    print("-- from JSON text")
    per_object(
        "json.loads + dataclass(**d)",
        lambda: Plain(**json.loads(TEXT)),
        plain,
    )
    per_object(
        "json.loads + Config(**d)",
        lambda: Config(**json.loads(TEXT)),
        plain,
    )
    per_object(
        "Model.model_validate_json(text)",
        lambda: Model.model_validate_json(TEXT),
        plain,
    )
    print("-- a bad value (limit=0): cost of the refusal")
    bad = {"limit": 0}

    def refuse_config() -> None:
        with contextlib.suppress(ConfigError):
            Config(**bad)

    def refuse_model() -> None:
        with contextlib.suppress(ValidationError):
            Model(**bad)

    per_object("Config(limit=0) raises ConfigError", refuse_config, None)
    per_object("Model(limit=0) raises ValidationError", refuse_model, None)


if __name__ == "__main__":
    main()

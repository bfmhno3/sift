"""rust_errors.py: how an error of the Rust side reaches Python.

A #[pyfunction] that returns PyResult<T> turns Err(PyErr) into a
raised exception, so a PyValueError built in Rust is an ordinary
ValueError with its message. The argument conversion is Rust code too
(FromPyObject) and raises on its own: TypeError for a wrong type,
OverflowError for -1 as a usize, UnicodeEncodeError for a lone
surrogate, which cannot become a Rust &str.
"""

from collections.abc import Callable
from typing import cast

import sift._rs as raw
from sift.ext import rs

# The stub says str; these calls pass what it forbids, on purpose.
tokenize_any = cast("Callable[..., object]", raw.tokenize)
tokenize_many_any = cast("Callable[..., object]", raw.tokenize_many)


def show(label: str, call: Callable[[], object]) -> None:
    """Print the exception that call raises, or its result."""
    try:
        result = call()
    except Exception as error:
        print(f"{label:34} {type(error).__name__}: {error}")
    else:
        print(f"{label:34} -> {result!r}")


def main() -> None:
    print("== PyResult::Err from Rust")
    show("tokenize_many(['a'], 257)", lambda: raw.tokenize_many(["a"], 257))
    show("tokenize_many(['a'], 256)", lambda: raw.tokenize_many(["a"], 256))
    try:
        rs.tokens_many(["a"], 1000)
    except ValueError as error:
        print(f"isinstance ValueError: {error!r}")

    print()
    print("== errors of the argument conversion")
    show("tokenize(b'abc')", lambda: tokenize_any(b"abc"))
    show("tokenize_many('abc')", lambda: tokenize_many_any("abc"))
    show("tokenize_many(['a'], -1)", lambda: tokenize_many_any(["a"], -1))
    show("tokenize('a\\ud800b')", lambda: raw.tokenize("a\ud800b"))

    print()
    print("== the wrapper repairs the surrogate and the offsets stay")
    text = "a\ud800中文"
    print(f"tokens({text!r}) = {rs.tokens(text)}")


if __name__ == "__main__":
    main()

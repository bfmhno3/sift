"""Types of the PyO3 module built from rust/sift-rs (make ext-rs)."""

# (text, position, start, end): what sift.analysis.tokenize.Token holds.
type _RawToken = tuple[str, int, int, int]

def tokenize(text: str) -> list[_RawToken]: ...
def tokenize_many(
    texts: list[str], threads: int = 0
) -> list[list[_RawToken]]: ...

# Debug builds only: raises pyo3_runtime.PanicException.
def panic_for_lab(message: str) -> None: ...

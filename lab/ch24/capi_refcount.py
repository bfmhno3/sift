"""capi_refcount.py: a C function that keeps its reference counts.

sift.ext._capi.count_cjk borrows its argument and returns a new
reference. If it leaked a reference, sys.getrefcount of the argument
would grow by one per call; if it dropped one too many, it would shrink
and the object would be freed under the caller. A million calls make
either visible.
"""

import contextlib
import sys

from sift.ext import _capi

CALLS = 1_000_000


def main() -> None:
    text = "搜索引擎 " * 3 + "sift"
    before = sys.getrefcount(text)
    for _ in range(CALLS):
        _capi.count_cjk(text)
    after = sys.getrefcount(text)
    print(f"getrefcount before {before}, after {CALLS} calls {after}")
    assert before == after, "count_cjk leaks or steals a reference"

    # The result is a new reference the caller owns.
    big = "中" * 100_000
    result = _capi.count_cjk(big)
    print("count_cjk of 100000 CJK characters:", result)

    # The error path must not leak either.
    bad = b"bytes"
    start = sys.getrefcount(bad)
    for _ in range(1000):
        with contextlib.suppress(TypeError):
            _capi.count_cjk(bad)
    print("refcount unchanged after TypeError:", start == sys.getrefcount(bad))


if __name__ == "__main__":
    main()

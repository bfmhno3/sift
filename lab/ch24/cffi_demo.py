"""cffi_demo.py: cffi in ABI mode and in API mode.

ABI mode (``ffi.dlopen``) loads a finished library and trusts the
declaration. API mode (``ffi.set_source`` and ``ffi.compile``) builds a
small extension module that includes the real header, so the compiler
checks the declaration, and calls then skip libffi.
"""

import importlib
import sys
import tempfile
from pathlib import Path

from cffi import FFI

from sift.ext import cffitok

ROOT = Path(__file__).resolve().parents[2]
CDEF = """
size_t sift_count_cjk(const char *utf8, size_t len);
"""


def abi_mode() -> None:
    print("== ABI mode: cdef + dlopen")
    ffi = FFI()
    ffi.cdef(CDEF)
    lib = ffi.dlopen(str(cffitok.LIBRARY))
    data = "搜索引擎 sift".encode()
    print("count_cjk:", lib.sift_count_cjk(data, len(data)))
    # A cdef that disagrees with the library is not detected: here the
    # size is passed as a 4-byte int. The call goes through, because
    # on x86-64 the register is wide enough, and a different ABI would
    # not be so kind.
    wrong = FFI()
    wrong.cdef("int sift_count_cjk(const char *utf8, int len);")
    other = wrong.dlopen(str(cffitok.LIBRARY))
    print("wrong cdef, same answer:", other.sift_count_cjk(data, len(data)))


def api_mode() -> None:
    print("== API mode: set_source + compile")
    ffi = FFI()
    ffi.cdef(CDEF)
    c_dir = str(ROOT / "c")
    ffi.set_source(
        "_sift_api_demo",
        '#include "sift_tok.h"',
        sources=[str(ROOT / "c" / "sift_tok.c")],
        include_dirs=[c_dir],
    )
    with tempfile.TemporaryDirectory() as tmp:
        built = ffi.compile(tmpdir=tmp, verbose=False)
        print("built:", Path(built).suffix)
        sys.path.insert(0, tmp)
        try:
            module = importlib.import_module("_sift_api_demo")
            data = "搜索引擎 sift".encode()
            print("count_cjk:", module.lib.sift_count_cjk(data, len(data)))
        finally:
            sys.path.remove(tmp)
            sys.modules.pop("_sift_api_demo", None)


def main() -> None:
    abi_mode()
    api_mode()


if __name__ == "__main__":
    main()

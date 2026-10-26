#!/usr/bin/env bash
# pyo3_hello.sh: the smallest PyO3 module (one #[pyfunction], one
#   #[pymodule]) built by `maturin develop` into a throwaway virtual
#   environment, imported and called; the output is out/ch25/
#   pyo3_hello.txt.
# stubs_check.sh: mypy --strict and pyright on a file that uses
#   sift._rs (clean), on one that misuses it (the errors the stub
#   catches), and mypy.stubtest, which compares src/sift/_rs.pyi with
#   the compiled module.
# index_tokenizers.sh: `sift index --full --tokenizer python|rust`,
#   each into its own index directory, and a cmp of the two
#   segment.sft files; then hyperfine of the two.
# Timings differ from run to run; the layout of the output does not.
set -euo pipefail

mkdir -p out/ch25
root=$(pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# --- pyo3_hello.sh --------------------------------------------------
pyo3_hello() {
    local crate="$work/hello"
    mkdir -p "$crate/src"
    cat > "$crate/Cargo.toml" << 'TOML'
[package]
name = "hello"
version = "0.1.0"
edition = "2024"

[lib]
name = "hello"
crate-type = ["cdylib"]

[dependencies]
pyo3 = "=0.30.1"
TOML
    cat > "$crate/pyproject.toml" << 'TOML'
[build-system]
requires = ["maturin>=1.9.4,<2"]
build-backend = "maturin"

[project]
name = "hello"
version = "0.1.0"
TOML
    cat > "$crate/src/lib.rs" << 'RUST'
use pyo3::prelude::*;

/// Greet `name` from Rust.
#[pyfunction]
fn greet(name: &str) -> String {
    format!("hello, {name}, from Rust")
}

#[pymodule]
fn hello(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(greet, m)?)
}
RUST
    echo '$ cat src/lib.rs'
    cat "$crate/src/lib.rs"
    python3 -m venv "$work/venv"
    echo '$ maturin develop   # in a new virtual environment'
    # Share the compiled dependencies with the real crate.
    (
        cd "$crate"
        export VIRTUAL_ENV="$work/venv" PATH="$work/venv/bin:$PATH"
        export CARGO_TARGET_DIR="$root/rust/sift-rs/target/hello"
        maturin develop 2>&1 | sed -E 's#/tmp/[^ ]*/#/tmp/.../#'
    )
    echo '$ python -c "import hello; ..."'
    "$work/venv/bin/python" - << 'PY'
import hello

print(hello.__file__.rsplit("/", 1)[-1])
print(hello.greet("Sift"))
print(hello.greet.__doc__)
print(hello.greet.__text_signature__)
PY
}
pyo3_hello 2>&1 | tee out/ch25/pyo3_hello.txt

# --- stubs_check.sh -------------------------------------------------
stubs_check() {
    cat > "$work/uses_rs_ok.py" << 'PY'
import sift._rs as rs

raw: list[tuple[str, int, int, int]] = rs.tokenize("c++ 中文")
many = rs.tokenize_many(["a", "b"], threads=2)
text: str = many[0][0][0]
PY
    cat > "$work/uses_rs_bad.py" << 'PY'
import sift._rs as rs

rs.tokenize(b"bytes")
rs.tokenize_many("abc")
rs.tokenize_many(["a"], threads="2")
count: int = rs.tokenize("a")
rs.no_such_function()
PY
    echo '$ mypy --strict uses_rs_ok.py'
    mypy --strict "$work/uses_rs_ok.py" | sed "s#$work/##"
    echo '$ mypy --strict uses_rs_bad.py   # five errors expected'
    local status=0
    mypy --strict "$work/uses_rs_bad.py" > "$work/mypy.txt" || status=$?
    sed "s#$work/##" "$work/mypy.txt"
    echo "mypy exit code: $status"
    echo '$ pyright uses_rs_ok.py'
    pyright "$work/uses_rs_ok.py" | sed "s#$work/##"
    echo '$ pyright uses_rs_bad.py'
    pyright "$work/uses_rs_bad.py" | sed "s#$work/##" || true
    echo '$ python -m mypy.stubtest sift._rs'
    # panic_for_lab exists in debug builds only: the release module
    # lacks it and stubtest reports it as missing at runtime. A
    # compiled module has no __all__.
    printf '%s\n' sift._rs.panic_for_lab sift._rs.__all__ \
        > "$work/allow.txt"
    python3 -m mypy.stubtest --allowlist "$work/allow.txt" sift._rs
}
stubs_check 2>&1 | tee out/ch25/stubs_check.txt

# --- index_tokenizers.sh --------------------------------------------
index_tokenizers() {
    local t
    for t in python rust; do
        echo "\$ SIFT_INDEX=idx-$t sift index --full --tokenizer $t"
        SIFT_INDEX="$work/idx-$t" sift index --full --tokenizer "$t" |
            sed 's/took [0-9.]* ms/took N ms/'
    done
    if cmp "$work/idx-python/segment.sft" "$work/idx-rust/segment.sft"; then
        echo "segment.sft python == rust: byte-identical"
    else
        echo "segment.sft python != rust: DIFFERENT"
        return 1
    fi
    echo "### sift index --full per tokenizer"
    local args=()
    for t in python rust; do
        args+=(-n "$t" "env SIFT_INDEX=$work/hf-$t python3 -m sift index --full --tokenizer $t")
    done
    hyperfine -N --warmup 1 --runs 5 "${args[@]}"
}
index_tokenizers 2>&1 | tee out/ch25/index_tokenizers.txt

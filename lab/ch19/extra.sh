#!/usr/bin/env bash
# startup_compare.sh, uv_demo, wheel_anatomy.sh, clean_venv_install.sh.
#
# startup_compare.sh: `sift --help` of tag ch18 (argparse) against this
#   tree (typer), hyperfine, the two taking turns in every round. Skipped
#   when the tag ch18 is not in the checkout.
# uv_demo: uv init --package, add, lock, run and tree in a temp dir, so
#   the repository stays clean; lab/ch19/uv_demo holds a copy of the
#   resulting pyproject.toml and uv.lock for reference. It needs the
#   network (PyPI); Python downloads stay off on Nix.
# wheel_anatomy.sh: build the sdist and the wheel, list and read them.
# clean_venv_install.sh: install the wheel in a new venv and search.
# The numbers differ from run to run; the layout of the output does not.
set -euo pipefail

mkdir -p out/ch19
root=$(pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export UV_PYTHON_DOWNLOADS=never
export UV_PYTHON=${UV_PYTHON:-python3.14}
export UV_CACHE_DIR="$work/uv-cache"
export UV_NO_PROGRESS=1

# --- startup_compare.sh ---------------------------------------------
startup_compare() {
    if ! git rev-parse -q --verify 'ch18^{commit}' > /dev/null; then
        echo "tag ch18 not found: startup comparison skipped"
        return 0
    fi
    mkdir "$work/ch18"
    git archive ch18 src | tar -x -C "$work/ch18"
    local old="env PYTHONPATH=$work/ch18/src python3 -m sift"
    local new="env PYTHONPATH=$root/src python3 -m sift"
    for arg in --help --version; do
        echo "### sift $arg: argparse (ch18) against typer (this tree)"
        for round in 1 2 3; do
            echo "== round $round"
            if (( round % 2 )); then
                hyperfine -N --warmup 3 --runs 20 \
                    -n "argparse ch18" "$old $arg" -n "typer ch19" "$new $arg"
            else
                hyperfine -N --warmup 3 --runs 20 \
                    -n "typer ch19" "$new $arg" -n "argparse ch18" "$old $arg"
            fi
        done
    done
    echo "### baseline"
    hyperfine -N --warmup 3 --runs 20 "python3 -c pass"
}
startup_compare 2>&1 | tee out/ch19/startup_compare.txt

# --- uv_demo --------------------------------------------------------
# A small project made by uv itself. `uv lock` runs twice: with an empty
# cache (the metadata of rich and its dependencies comes from PyPI) and
# with the cache filled.
uv_demo() {
    local demo="$work/uv-project"
    unset VIRTUAL_ENV
    mkdir "$demo"
    cd "$demo"
    uv --version
    echo '$ uv init --package --vcs none --name uv-demo'
    uv init --package --vcs none --name uv-demo
    echo '$ uv add rich'
    uv add rich
    echo '$ uv lock   # cache already filled by uv add'
    TIMEFORMAT='uv lock, warm cache: %R s'
    time uv lock
    rm uv.lock
    rm -rf "$UV_CACHE_DIR"
    TIMEFORMAT='uv lock, empty cache: %R s'
    time uv lock
    echo '$ uv run uv-demo'
    uv run uv-demo
    echo '$ uv tree'
    uv tree
    echo '$ cat pyproject.toml'
    cat pyproject.toml
    echo '$ head -n 20 uv.lock'
    head -n 20 uv.lock
    echo '--- diff against lab/ch19/uv_demo (versions move with PyPI) ---'
    diff -u "$root/lab/ch19/uv_demo/pyproject.toml" pyproject.toml || true
    diff -u "$root/lab/ch19/uv_demo/uv.lock" uv.lock | head -n 20 || true
    cd "$root"
}
uv_demo 2>&1 | tee out/ch19/uv_demo.txt

# --- wheel_anatomy.sh -----------------------------------------------
# python -m build makes the sdist from the tree and the wheel from the
# sdist. --no-isolation uses hatchling of the dev shell instead of
# fetching one.
wheel_anatomy() {
    local dist="$root/out/ch19/dist"
    rm -rf "$dist"
    echo '$ python -m build --no-isolation --outdir out/ch19/dist'
    python3 -m build --no-isolation --outdir "$dist" .
    local wheel sdist
    wheel=$(ls "$dist"/*.whl)
    sdist=$(ls "$dist"/*.tar.gz)
    echo
    echo '$ ls -l out/ch19/dist'
    ls -l "$dist"
    echo
    echo "wheel size: $(stat -c %s "$wheel") bytes"
    echo "sdist size: $(stat -c %s "$sdist") bytes"
    echo
    echo "\$ unzip -l $(basename "$wheel")"
    unzip -l "$wheel"
    echo
    echo "\$ tar tzf $(basename "$sdist")"
    tar tzf "$sdist"
    for member in METADATA WHEEL entry_points.txt RECORD; do
        echo
        echo "\$ unzip -p $(basename "$wheel") '*.dist-info/$member'"
        unzip -p "$wheel" "*.dist-info/$member"
    done
    echo
    echo '$ unzip -l | grep -c __pycache__   # no bytecode in the wheel'
    unzip -l "$wheel" | grep -c __pycache__ || true
}
wheel_anatomy 2>&1 | tee out/ch19/wheel_anatomy.txt

# --- clean_venv_install.sh ------------------------------------------
# A venv with nothing in it, the wheel and its dependencies from PyPI,
# and a search over an index that the installed program builds itself.
clean_venv_install() {
    local venv="$work/sift-venv"
    local wheel
    wheel=$(ls "$root"/out/ch19/dist/*.whl)
    echo "\$ uv venv $venv"
    uv venv "$venv"
    echo "\$ uv pip install $(basename "$wheel")"
    TIMEFORMAT='uv pip install: %R s'
    time uv pip install --python "$venv/bin/python" "$wheel"
    echo '$ uv pip list'
    uv pip list --python "$venv/bin/python"
    echo '$ python -c "import sift, rich; print(sift.__file__, rich.__file__)"'
    "$venv/bin/python" -c \
        "import sift, rich; print(sift.__file__); print(rich.__file__)"
    export SIFT_INDEX="$work/idx"
    echo '$ sift index --corpus corpus/posts'
    "$venv/bin/sift" index --corpus corpus/posts
    echo '$ sift --version'
    "$venv/bin/sift" --version
    echo '$ sift search kalman'
    "$venv/bin/sift" search --limit 3 kalman
}
clean_venv_install 2>&1 | tee out/ch19/clean_venv_install.txt

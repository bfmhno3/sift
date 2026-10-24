#!/usr/bin/env bash
# What the checkers say: reveal_type notes, and the six errors of
# bad_types.py in mypy and pyright (both must exit 1).
set -euo pipefail

mkdir -p out/ch14

# reveal_type notes: mypy exits 0 on notes alone.
mypy lab/ch14/reveal_types.py > out/ch14/reveal_types.mypy
cat out/ch14/reveal_types.mypy

# bad_types.py: `|| status=$?` keeps set -e from stopping the script.
status=0
mypy --strict lab/ch14/bad_types.py \
    > out/ch14/bad_types.mypy || status=$?
if [ "$status" -ne 1 ]; then
    echo "mypy exited $status on bad_types.py, expected 1" >&2
    exit 1
fi
status=0
# pyright prints absolute paths; strip the repo root from the saved copy.
pyright lab/ch14/bad_types.py \
    > out/ch14/bad_types.pyright.raw || status=$?
sed "s|$PWD/||g" out/ch14/bad_types.pyright.raw \
    > out/ch14/bad_types.pyright
rm out/ch14/bad_types.pyright.raw
if [ "$status" -ne 1 ]; then
    echo "pyright exited $status on bad_types.py, expected 1" >&2
    exit 1
fi
sed -n 1,20p out/ch14/bad_types.mypy
sed -n 1,30p out/ch14/bad_types.pyright

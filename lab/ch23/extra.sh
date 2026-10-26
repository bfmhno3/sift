#!/usr/bin/env bash
# pyinstrument_index.sh: a sampling profile of `sift index --full`, as
#   text (out/ch23/pyinstrument.txt).
# py_spy.sh: py-spy samples the same run from outside and draws a flame
#   graph, out/figures/ch23-flame.svg. If ptrace is denied the error is
#   saved in out/ch23/py_spy.txt and the step is skipped.
# line_profiler_tokenize.sh: `kernprof -l -v` on iter_tokens. kernprof is
#   not in the flake; without it the step prints a line and moves on.
# memray_index.sh: `memray run` and `memray stats` of the same run.
# bench_profile.sh: `sift bench search --profile` writes
#   out/profile.pstats; its first lines are printed.
# before_after.sh: hyperfine of tag ch22 (a temporary worktree) against
#   this tree for `sift index --full` and `sift bench search`, and a cmp
#   of the two segment files.
# Timings differ from run to run; the layout of the output does not.
set -euo pipefail

mkdir -p out/ch23 out/figures
root=$(pwd)
work=$(mktemp -d)
cleanup() {
    git worktree remove --force "$work/ch22" 2> /dev/null || true
    git worktree prune
    rm -rf "$work"
}
trap cleanup EXIT
export SIFT_INDEX="$work/idx"

# --- pyinstrument_index.sh ------------------------------------------
# A sampling profiler looks at the stack every millisecond instead of
# hooking every call, so it costs little and shows the call tree.
pyinstrument_index() {
    if ! python3 -c 'import pyinstrument' 2> /dev/null; then
        echo "pyinstrument unavailable: not importable, skipped"
        return 0
    fi
    echo '$ python3 -m pyinstrument -r text -m sift index --full'
    python3 -m pyinstrument -r text --no-color \
        -o out/ch23/pyinstrument-tree.txt -m sift index --full
    head -n 45 out/ch23/pyinstrument-tree.txt
}
pyinstrument_index 2>&1 | tee out/ch23/pyinstrument.txt

# --- py_spy.sh ------------------------------------------------------
py_spy() {
    if ! command -v py-spy > /dev/null; then
        echo "py-spy unavailable: not in PATH, skipped"
        return 0
    fi
    py-spy --version
    echo '$ py-spy record --duration 15 -o out/figures/ch23-flame.svg -- python3 -m sift index --full'
    local status=0
    rm -f out/figures/ch23-flame.svg
    # --duration ends the recording when py-spy does not see the child
    # exit (it never does under make); the run takes about 3 s.
    timeout 60 py-spy record --duration 15 -o out/figures/ch23-flame.svg -- \
        python3 -m sift index --full 2> "$work/py-spy.err" || status=$?
    if [[ -s out/figures/ch23-flame.svg ]]; then
        tail -n 3 "$work/py-spy.err"
        ls -l out/figures/ch23-flame.svg
        if ((status != 0)); then
            # py-spy 0.4.2 sometimes fails its last waitpid with
            # ECHILD once the profiled process has exited; the graph
            # is complete by then.
            echo "py-spy exit $status after writing the graph"
        fi
    else
        echo "py-spy failed (exit $status), skipped. Error:"
        cat "$work/py-spy.err"
        rm -f out/figures/ch23-flame.svg
    fi
}
py_spy 2>&1 | tee out/ch23/py_spy.txt

# --- line_profiler_tokenize.sh --------------------------------------
# kernprof injects `profile` into builtins; the script wraps iter_tokens
# with it and tokenizes the corpus.
line_profiler_tokenize() {
    if ! command -v kernprof > /dev/null; then
        echo "kernprof unavailable: line-profiler is not in the flake, skipped"
        return 0
    fi
    cat > "$work/line_tokenize.py" << PY
from pathlib import Path

from sift.analysis import tokenize
from sift.corpus import iter_documents

traced = profile(tokenize.iter_tokens)  # noqa: F821
for doc in iter_documents(Path("$root/corpus/posts")):
    for _ in traced(doc.body):
        pass
PY
    echo '$ kernprof -l -v line_tokenize.py'
    (cd "$work" && kernprof -l -v line_tokenize.py)
}
line_profiler_tokenize 2>&1 | tee out/ch23/line_profiler.txt

# --- memray_index.sh ------------------------------------------------
memray_index() {
    if ! python3 -c 'import memray' 2> /dev/null; then
        echo "memray unavailable: not importable, skipped"
        return 0
    fi
    echo '$ python3 -m memray run -m sift index --full'
    python3 -m memray run -f -o "$work/index.bin" -m sift index --full
    echo '$ python3 -m memray stats index.bin'
    python3 -m memray stats "$work/index.bin"
}
memray_index 2>&1 | tee out/ch23/memray.txt

# --- bench_profile.sh -----------------------------------------------
bench_profile() {
    sift index --full > /dev/null
    echo '$ sift bench search --profile'
    sift bench search --profile
    python3 - << 'PY'
import pstats

stats = pstats.Stats("out/profile.pstats").strip_dirs()
print("== out/profile.pstats, sorted by own time, top 8")
stats.sort_stats(pstats.SortKey.TIME).print_stats(8)
PY
}
bench_profile 2>&1 | tee out/ch23/bench_profile.txt

# --- before_after.sh ------------------------------------------------
# Both trees run from this directory (sift.toml, corpus, bench queries);
# PYTHONPATH puts the src of the tree under test first.
before_after() {
    if ! git rev-parse -q --verify 'ch22^{commit}' > /dev/null; then
        echo "tag ch22 not found: comparison skipped"
        return 0
    fi
    git worktree add --detach -q "$work/ch22" ch22
    local old="env PYTHONPATH=$work/ch22/src SIFT_INDEX=$work/idx-old"
    local new="env PYTHONPATH=$root/src SIFT_INDEX=$work/idx-new"
    echo "### sift index --full: ch22 against HEAD"
    hyperfine -N --warmup 1 --runs 5 --export-json "$work/index.json" \
        -n "ch22" "$old python3 -m sift index --full" \
        -n "HEAD" "$new python3 -m sift index --full"
    echo "### sift bench search: ch22 against HEAD"
    hyperfine -N --warmup 1 --runs 5 --export-json "$work/search.json" \
        -n "ch22" "$old python3 -m sift bench search" \
        -n "HEAD" "$new python3 -m sift bench search"
    python3 - "$work/index.json" "$work/search.json" << 'PY'
import json
import sys

for label, path in zip(("index --full", "bench search"), sys.argv[1:]):
    old, new = json.load(open(path))["results"]
    print(
        f"{label}: ch22 {old['mean']:.3f} s, HEAD {new['mean']:.3f} s, "
        f"speedup {old['mean'] / new['mean']:.2f}x"
    )
PY
    echo "### segment.sft of ch22 against HEAD"
    if cmp "$work/idx-old/segment.sft" "$work/idx-new/segment.sft"; then
        echo "byte-identical"
    else
        echo "DIFFERENT"
        return 1
    fi
}
before_after 2>&1 | tee out/ch23/before_after.txt

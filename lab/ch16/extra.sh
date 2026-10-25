#!/usr/bin/env bash
# bench_index.sh: parallel indexing, jobs x mode, on the standard build
# (python3, GIL) and thread mode on the free-threaded build (python3.14t).
# The venv belongs to python3, so python3.14t runs the source tree with
# PYTHONPATH=src; `sift bench index` needs no SQLAlchemy. Since ch19 the
# command line needs typer and rich, which python3.14t does not have:
# their pure-Python packages are linked from the python3 environment
# into a temporary directory that is added to PYTHONPATH.
# The timings differ from run to run; the table layout does not.
set -euo pipefail

mkdir -p out/ch16
pure=$(mktemp -d)
trap 'rm -rf "$pure"' EXIT
python3 - "$pure" <<'PY'
import importlib.util
import os
import sys

for name in (
    "typer", "click", "rich", "markdown_it", "mdurl", "pygments",
    "shellingham", "annotated_doc",
):
    spec = importlib.util.find_spec(name)
    assert spec is not None and spec.origin is not None, name
    package = os.path.dirname(spec.origin)
    os.symlink(package, os.path.join(sys.argv[1], name))
PY
ARGS=(bench index --repeat 8 --jobs 1,2,4,8 --rounds 2)

{
    echo "$ python3 -m sift ${ARGS[*]} --mode process,thread,interp"
    python3 -m sift "${ARGS[@]}" --mode process,thread,interp
} | tee out/ch16/bench_index.python3.txt

{
    echo "$ PYTHONPATH=src:<pure-Python typer and rich> python3.14t -m sift ${ARGS[*]} --mode thread"
    PYTHONPATH="src:$pure" python3.14t -m sift "${ARGS[@]}" --mode thread
} | tee out/ch16/bench_index.python3.14t.txt

# Single-thread cost of the free-threaded build: the jobs=1 row is the
# serial build, no pool, so the two numbers differ only by the build.
seconds() {
    awk '$1 == 1 && $3 == "s" {print $2; exit}' "$1"
}
gil=$(seconds out/ch16/bench_index.python3.txt)
free=$(seconds out/ch16/bench_index.python3.14t.txt)
awk -v gil="$gil" -v free="$free" 'BEGIN {
    printf "serial build, 1 thread: python3 %.3f s, python3.14t %.3f s, "\
           "python3.14t / python3 = %.2f\n", gil, free, free / gil
}' | tee out/ch16/single_thread_overhead.txt

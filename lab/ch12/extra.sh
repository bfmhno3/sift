#!/usr/bin/env bash
# incremental_index.sh: what `sift index` reparses after a change.
# Then two timing sections (python3 heredocs): cold vs incremental
# `sift index`, and `sift search` on the mmap segment vs a rebuild.
# Everything runs on a copy of the corpus and an index in a temp dir.
set -euo pipefail

mkdir -p out/ch12
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export SIFT_INDEX="$work/idx"
cp -r corpus/posts "$work/posts"
target="$work/posts/$(ls "$work/posts" | sed -n 1p)"

# --- incremental_index.sh: index, touch, edit, delete, add ----------
{
    echo "$ sift index --corpus <copy>          # cold"
    sift index --corpus "$work/posts"
    echo
    echo "$ sift index --corpus <copy>          # nothing changed"
    sift index --corpus "$work/posts"
    echo
    echo "$ touch one file                      # mtime only, same bytes"
    sleep 0.01
    touch "$target"
    sift index --corpus "$work/posts"
    echo
    echo "$ append a line to one file           # new sha256"
    printf '\nzymurgy marker line\n' >> "$target"
    sift index --corpus "$work/posts"
    echo "$ sift search zymurgy                 # the new word is found"
    sift search --limit 1 zymurgy | sed -n '$p'
    echo
    echo "$ delete one file and add one"
    rm "$work/posts/$(ls "$work/posts" | sed -n 2p)"
    printf -- '---\ntitle: Fresh\npublished: 2026-03-01\n---\nhello\n' \
        > "$work/posts/zz-fresh.md"
    sift index --corpus "$work/posts"
    echo
    echo "$ sift index --full --corpus <copy>"
    sift index --full --corpus "$work/posts"
} 2>&1 | tee out/ch12/incremental_index.txt

# --- index_timing: cold vs incremental, alternating rounds ----------
WORK="$work" python3 - <<'PY' | tee out/ch12/index_timing.txt
import os
import statistics
import subprocess
import time
from pathlib import Path

work = Path(os.environ["WORK"])
posts = work / "posts"
target = sorted(posts.glob("*.md"))[0]
base = ["sift", "index", "--corpus", str(posts)]
ROUNDS = 5


def run(args: list[str]) -> float:
    start = time.perf_counter()
    subprocess.run(args, check=True, capture_output=True)
    return (time.perf_counter() - start) * 1000


times: dict[str, list[float]] = {
    "cold (--full)": [],
    "incremental, nothing changed": [],
    "incremental, 1 file changed": [],
    "python3 -c 'import sift.cli' (startup)": [],
}
for i in range(ROUNDS):
    times["cold (--full)"].append(run([*base, "--full"]))
    times["incremental, nothing changed"].append(run(base))
    with target.open("a", encoding="utf-8") as file:
        file.write(f"\nround {i}\n")
    times["incremental, 1 file changed"].append(run(base))
    times["python3 -c 'import sift.cli' (startup)"].append(
        run(["python3", "-c", "import sift.cli"])
    )
print(f"wall clock of one `sift index` process, {ROUNDS} alternating rounds")
for name, ms in times.items():
    print(
        f"{name:<40} min {min(ms):7.0f} ms  "
        f"median {statistics.median(ms):7.0f} ms"
    )
cold = statistics.median(times["cold (--full)"])
inc = statistics.median(times["incremental, 1 file changed"])
print(f"cold / incremental (medians): {cold / inc:.1f}x")
PY

# --- search_latency: mmap segment vs the ch08 full rebuild ----------
sift index --corpus "$work/posts" --full > /dev/null
WORK="$work" python3 - <<'PY' | tee out/ch12/search_latency.txt
import os
import statistics
import subprocess
import time

ROUNDS = 7
query = "rust 所有权"
rebuild = (
    "from sift.analysis import build_pipeline;"
    "from sift.cli import load_index;"
    "from sift.search import Searcher;"
    "from pathlib import Path;"
    "p = build_pipeline(['mixed', 'nfkc', 'stopwords']);"
    f"_, i = load_index(Path({os.environ['WORK'] + '/posts'!r}), p);"
    f"print(Searcher(i, pipeline=p).search({query!r}).total)"
)
commands = {
    "sift search (mmap segment)": ["sift", "search", "--limit", "3", query],
    "rebuild index, then search (ch08)": ["python3", "-c", rebuild],
    "python3 -c 'import sift.cli' (startup)": [
        "python3",
        "-c",
        "import sift.cli",
    ],
}
times: dict[str, list[float]] = {name: [] for name in commands}
for _ in range(ROUNDS):
    for name, argv in commands.items():
        start = time.perf_counter()
        subprocess.run(argv, check=True, capture_output=True)
        times[name].append((time.perf_counter() - start) * 1000)
print(
    f"query {query!r}: wall clock of one process, "
    f"{ROUNDS} alternating rounds"
)
for name, ms in times.items():
    print(
        f"{name:<40} min {min(ms):7.0f} ms  "
        f"median {statistics.median(ms):7.0f} ms"
    )
a = statistics.median(times["rebuild index, then search (ch08)"])
b = statistics.median(times["sift search (mmap segment)"])
print(f"rebuild / mmap (medians): {a / b:.1f}x")
PY
sift search --limit 3 "rust 所有权" | sed -n '$p' \
    | tee out/ch12/search_breakdown.txt

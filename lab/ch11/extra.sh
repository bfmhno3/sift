#!/usr/bin/env bash
# Import cost, the CLI exit codes, and cold vs warm startup of the
# installed `sift` command.
set -euo pipefail

mkdir -p out/ch11

# 从 ch12 起 search/show/stats 读磁盘上的索引：建在临时目录里。
SIFT_INDEX=$(mktemp -d)
export SIFT_INDEX
trap 'rm -rf "$SIFT_INDEX"' EXIT
sift index > /dev/null

# --- import_trace.sh: what `import sift.search` pulls in -------------
# Format of -X importtime: self [us] | cumulative [us] | module name,
# children indented under their importer. Sort by cumulative time.
python3 -X importtime -c 'import sift.search' \
    2> out/ch11/importtime.raw
echo "top 15 imports by cumulative time (us):" \
    | tee out/ch11/import_trace.txt
grep '|' out/ch11/importtime.raw \
    | grep -v 'cumulative' \
    | sort -t'|' -k2 -n -r \
    | sed -n 1,15p \
    | tee -a out/ch11/import_trace.txt
echo "sift modules only:" | tee -a out/ch11/import_trace.txt
grep -E '\| +sift(\.| *$)' out/ch11/importtime.raw \
    | tee -a out/ch11/import_trace.txt
total=$(grep -E '\| +sift\.search$' out/ch11/importtime.raw \
    | awk -F'|' '{gsub(/ /, "", $2); print $2}')
echo "cumulative import of sift.search: ${total} us" \
    | tee -a out/ch11/import_trace.txt

# --- cli_exit_codes.sh: one command per exit code --------------------
# A failing command must not stop the script, so each one is run in
# `if` position and its status is read from $?.
report() {
    local expect=$1 status=0
    shift
    "$@" > out/ch11/last.stdout 2> out/ch11/last.stderr || status=$?
    printf '%-52s -> %s (expected %s)\n' "$*" "$status" "$expect"
    sed 's/^/    stderr: /' out/ch11/last.stderr | sed -n 1,3p
    [ "$status" -eq "$expect" ]
}
{
    report 0 sift --version
    report 0 sift search --limit 3 rust
    report 0 sift search zzzzqqqq
    report 2 sift search
    report 2 sift bench
    report 3 sift search '(rust'
    report 3 sift search 'a AND'
    report 1 sift show 999999
    report 4 env SIFT_INDEX=/nonexistent sift search rust
    report 4 env SIFT_INDEX=/nonexistent sift stats
} 2>&1 | tee out/ch11/cli_exit_codes.txt
rm -f out/ch11/last.stdout out/ch11/last.stderr

# --- cold vs warm startup of `sift --version` ------------------------
# Cold: the .pyc files of sift are deleted before every run, so the
# interpreter compiles every module it imports (and writes the .pyc).
# Warm: the .pyc files exist. The standard library is warm in both.
hyperfine --warmup 3 --runs 30 \
    --export-json out/ch11/startup.json \
    --command-name 'cold (no sift .pyc)' \
    --prepare 'find src -name __pycache__ -prune -exec rm -rf {} +' \
    'sift --version' \
    --command-name 'warm (.pyc present)' \
    --prepare 'true' \
    'sift --version' \
    | tee out/ch11/startup.txt
python3 - <<'PY'
import json

with open("out/ch11/startup.json") as f:
    cold, warm = (r["mean"] for r in json.load(f)["results"])
print(f"cold/warm: {cold / warm:.2f}x ({cold*1000:.1f} ms vs "
      f"{warm*1000:.1f} ms)")
PY

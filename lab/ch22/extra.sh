#!/usr/bin/env bash
# figures: `sift bench search` five times logs 60 queries in a fresh
#   index, then `sift report --out out/report` draws the four PNGs and
#   report.md; the PNGs are copied to out/figures/ch22-*.png.
# `sift similar 0` and the report table go to out/ch22/numbers.txt.
set -euo pipefail

mkdir -p out/ch22 out/figures
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export SIFT_INDEX="$work/idx"
sift index --corpus corpus/posts > "$work/index.txt"

for _ in 1 2 3 4 5; do
    sift bench search > /dev/null
done

{
    echo '$ sift similar 0'
    sift similar 0
    echo
    echo '$ sift report'
    sift report --out out/report
    echo
    cat out/report/report.md
} 2>&1 | tee out/ch22/numbers.txt

for name in zipf heaps posts-per-month latency-hist; do
    cp "out/report/$name.png" "out/figures/ch22-$name.png"
    test -s "out/figures/ch22-$name.png"
done

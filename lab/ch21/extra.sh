#!/usr/bin/env bash
# screenshots: qt_screenshot.py four times into out/figures, offscreen
#   at a scale factor of 2 (2400x1520 px): rust 所有权 in light and dark
#   with the first result selected, the empty state (light) and the
#   syntax error "(rust" (dark). Each PNG becomes a WebP with
#   `magick in.png -quality 90 out.webp`; each WebP must stay under
#   400 KB.
# The numbers (first paint, request to rows, frame interval) go to
#   out/ch21/numbers.txt; they differ from run to run.
set -euo pipefail

export QT_QPA_PLATFORM=offscreen
mkdir -p out/ch21 out/figures
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export SIFT_INDEX="$work/idx"
sift index --corpus corpus/posts > "$work/index.txt"

LIMIT=400000

shoot() {
    local name=$1
    shift
    local png=out/figures/ch21-qt-$name.png
    local webp=out/figures/ch21-qt-$name.webp
    python3 lab/ch21/qt_screenshot.py "$@" --out "$png"
    magick "$png" -quality 90 "$webp"
    local size
    size=$(stat -c %s "$webp")
    if (( size > LIMIT )); then
        echo "$webp is $size bytes, over $LIMIT" >&2
        return 1
    fi
    echo "$webp: $size bytes"
}

{
    shoot light --theme light --query 'rust 所有权' --select 0
    shoot dark --theme dark --query 'rust 所有权' --select 0
    shoot empty --theme light --query ''
    shoot error --theme dark --query '(rust'
} 2>&1 | tee out/ch21/numbers.txt

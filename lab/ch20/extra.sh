#!/usr/bin/env bash
# screenshots: tk_screenshot_gui.py twice (light, dark) on a virtual
#   screen of 1100x700, query "rust 所有权", into out/figures. Each PNG
#   must stay under 400 KB; the file is re-written with `convert` if
#   it does not.
# enter_to_paint: the time from Enter in the entry to the rows on the
#   screen, a few queries, median of five runs each.
# The window needs a display, so both run under xvfb-run. The numbers
# differ from run to run; the layout of the output does not.
set -euo pipefail

mkdir -p out/ch20 out/figures
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export SIFT_INDEX="$work/idx"
sift index --corpus corpus/posts > "$work/index.txt"

screen() {
    xvfb-run -a -s "-screen 0 1100x700x24" "$@"
}

LIMIT=400000
shrink() {
    local png=$1
    local size
    size=$(stat -c %s "$png")
    if (( size > LIMIT )); then
        convert "$png" -colors 256 -strip \
            -define png:compression-level=9 "$png"
        size=$(stat -c %s "$png")
    fi
    if (( size > LIMIT )); then
        echo "$png is $size bytes, over $LIMIT" >&2
        return 1
    fi
    echo "$png: $size bytes"
}

{
    for theme in light dark; do
        out=out/figures/ch20-tk-$theme.png
        screen python3 lab/ch20/tk_screenshot_gui.py \
            --theme "$theme" --query 'rust 所有权' --out "$out"
        shrink "$out"
        identify "$out"
    done
} 2>&1 | tee out/ch20/screenshots.txt

screen python3 lab/ch20/enter_to_paint.py 2>&1 | tee out/ch20/enter_to_paint.txt

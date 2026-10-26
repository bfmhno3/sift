#!/usr/bin/env bash
# c_warnings.sh: sift_tok.c and sift_capi.c compile with -Wall -Wextra
#   -Werror; the output is out/ch24/c_warnings.txt.
# sanitize_fuzz.sh: sift_tok.c under AddressSanitizer and UBSan, fed
#   200000 random byte strings by lab/ch24/sanitize_fuzz.c.
# segfault_exit.sh: runs ctypes_segfault_fail.py by hand and saves the
#   shell's exit code (128 + SIGSEGV) next to the one the runner sees.
# cython_annotate.sh: `cython -a` writes out/ch24/_cytok.html; the
#   yellow lines (score above 0) are counted, in total and per function.
# index_tokenizers.sh: `sift index --full --tokenizer python|c|cffi|
#   cython`, each into its own index directory, and a cmp of every
#   segment.sft against the Python one; then hyperfine of the four.
# Timings differ from run to run; the layout of the output does not.
set -euo pipefail

mkdir -p out/ch24
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
python_include=$(python3-config --includes)

# --- c_warnings.sh --------------------------------------------------
c_warnings() {
    echo '$ gcc -O2 -Wall -Wextra -Werror -fPIC -c sift_tok.c'
    gcc -O2 -Wall -Wextra -Werror -fPIC -c c/sift_tok.c -o "$work/tok.o"
    echo '$ gcc -O2 -Wall -Wextra -Werror -fPIC -c sift_capi.c'
    # shellcheck disable=SC2086
    gcc -O2 -Wall -Wextra -Werror -fPIC $python_include \
        -c c/sift_capi.c -o "$work/capi.o"
    echo "no warnings"
    echo '$ nm -D --defined-only c/build/libsifttok.so'
    nm -D --defined-only c/build/libsifttok.so | grep ' T '
}
c_warnings 2>&1 | tee out/ch24/c_warnings.txt

# --- sanitize_fuzz.sh -----------------------------------------------
sanitize_fuzz() {
    echo '$ gcc -fsanitize=address,undefined sanitize_fuzz.c sift_tok.c'
    gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all \
        -Wall -Wextra -Ic -o "$work/fuzz" \
        lab/ch24/sanitize_fuzz.c c/sift_tok.c
    "$work/fuzz"
}
sanitize_fuzz 2>&1 | tee out/ch24/sanitize_fuzz.txt

# --- segfault_exit.sh -----------------------------------------------
segfault_exit() {
    local status=0
    # The braces keep bash from announcing the signal on our stderr.
    {
        python3 lab/ch24/ctypes_segfault_fail.py > "$work/segv.out" \
            2> "$work/segv.err" || status=$?
    } 2> /dev/null
    echo "shell exit code: $status (128 + SIGSEGV 11)"
    echo "subprocess.run sees: $(python3 -c '
import subprocess, sys
p = subprocess.run([sys.executable, "lab/ch24/ctypes_segfault_fail.py"],
                   capture_output=True)
print(p.returncode)')"
    echo "--- stdout"
    cat "$work/segv.out"
    echo "--- stderr, the faulthandler part"
    sed -n '1,/^Current thread.s C stack/p' "$work/segv.err" |
        sed '$d'
}
segfault_exit 2>&1 | tee out/ch24/segfault_exit.txt

# --- cython_annotate.sh ---------------------------------------------
cython_annotate() {
    echo '$ cython -3 -a src/sift/ext/_cytok.pyx'
    cython -3 -a src/sift/ext/_cytok.pyx -o "$work/_cytok.c"
    cp "$work/_cytok.html" out/ch24/_cytok.html
    python3 - << 'PY'
import re
from pathlib import Path

html = Path("out/ch24/_cytok.html").read_text(encoding="utf-8")
source = Path("src/sift/ext/_cytok.pyx").read_text(encoding="utf-8")
lines = source.splitlines()
pattern = re.compile(
    r'<pre class="cython line score-(\d+)"[^>]*>.<span class="">(\d+)</span>'
)
yellow = {int(n): int(s) for s, n in pattern.findall(html) if int(s) > 0}

def span_of(name: str) -> range:
    """Return the line numbers of the def called name."""
    start = next(
        i for i, text in enumerate(lines, 1) if text.startswith(f"def {name}(")
    )
    end = start
    for i in range(start + 1, len(lines) + 1):
        text = lines[i - 1]
        if text and not text[0].isspace():
            break
        end = i
    return range(start, end + 1)

print(f"lines in the .pyx: {len(lines)}")
print(f"yellow lines in total: {len(yellow)}")
for name in ("tokens", "count_cjk", "count_cjk_utf8"):
    inside = sorted(n for n in yellow if n in span_of(name))
    print(f"yellow lines in {name}(): {len(inside)}")
print("yellow lines of tokens(), with their scores:")
for n in sorted(n for n in yellow if n in span_of("tokens")):
    print(f"  {n:3} score {yellow[n]:3}  {lines[n - 1].strip()}")
PY
}
cython_annotate 2>&1 | tee out/ch24/cython_annotate.txt

# --- index_tokenizers.sh --------------------------------------------
index_tokenizers() {
    local t
    for t in python c cffi cython; do
        echo "\$ SIFT_INDEX=idx-$t sift index --full --tokenizer $t"
        SIFT_INDEX="$work/idx-$t" sift index --full --tokenizer "$t" |
            sed 's/took [0-9.]* ms/took N ms/'
    done
    for t in c cffi cython; do
        if cmp "$work/idx-python/segment.sft" "$work/idx-$t/segment.sft"; then
            echo "segment.sft python == $t: byte-identical"
        else
            echo "segment.sft python != $t: DIFFERENT"
            return 1
        fi
    done
    echo "### sift index --full per tokenizer"
    local args=()
    for t in python c cffi cython; do
        args+=(-n "$t" "env SIFT_INDEX=$work/hf-$t python3 -m sift index --full --tokenizer $t")
    done
    hyperfine -N --warmup 1 --runs 5 "${args[@]}"
}
index_tokenizers 2>&1 | tee out/ch24/index_tokenizers.txt

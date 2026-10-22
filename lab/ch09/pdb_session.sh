#!/usr/bin/env bash
# Drive python -m pdb without a terminal: the commands come from stdin.
# Run from the repository root; the output goes to stdout.
set -uo pipefail

TARGET=lab/ch09/helpers/pdb_target.py

echo '### 1. breakpoint on mean(): b, c, p, w, n, q'
printf '%s\n' 'b mean' c 'p values' w n n n 'p total' q \
    | python3 -m pdb "$TARGET" 2>&1
echo

echo '### 2. post-mortem: -c continue runs to the crash, then w, p, u'
printf '%s\n' w 'p values' u 'p __name__' q \
    | python3 -m pdb -c continue "$TARGET" 2>&1
echo

echo '### 3. breakpoint() in the code stops in pdb by default'
printf '%s\n' 'p __name__' c \
    | python3 "$TARGET" --breakpoint 2>&1
echo

echo '### 4. PYTHONBREAKPOINT=0 turns every breakpoint() into a no-op'
PYTHONBREAKPOINT=0 python3 "$TARGET" --breakpoint 2>&1
exit 0

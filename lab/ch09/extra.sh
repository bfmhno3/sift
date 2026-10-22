#!/usr/bin/env bash
# Experiments that need a shell: warnings as errors, colored
# tracebacks, pdb driven by stdin, and the PEP 768 remote attach.
set -euo pipefail

mkdir -p out/ch09

# PEP 765: the compiler warns about `return` in `finally`; with
# -W error the warning becomes a SyntaxError and the script fails.
python3 -W error lab/ch09/finally_return_warning.py \
    > out/ch09/finally_return_warning.werror.txt 2>&1 \
    && echo "unexpected: -W error did not fail" >&2 \
    || true
cat out/ch09/finally_return_warning.werror.txt

# 3.14 error messages: suggestions and (with FORCE_COLOR) colors.
for typo in \
    'import math; print(math.sqroot(2))' \
    'print(undefined_name)' \
    'from math import sqroot' \
    'whille True: pass' \
    'x = {"a": 1}; x["b"]'; do
    echo "--- python3 -c '$typo'"
    python3 -c "$typo" 2>&1 || true
done > out/ch09/traceback_typos.txt
cat out/ch09/traceback_typos.txt
env -u NO_COLOR FORCE_COLOR=1 \
    python3 -c 'import math; print(math.sqroot(2))' \
    > out/ch09/traceback_typo.color.txt 2>&1 || true
env -u FORCE_COLOR NO_COLOR=1 \
    python3 -c 'import math; print(math.sqroot(2))' \
    > out/ch09/traceback_typo.nocolor.txt 2>&1 || true
echo "colored bytes: $(wc -c < out/ch09/traceback_typo.color.txt)," \
    "plain bytes: $(wc -c < out/ch09/traceback_typo.nocolor.txt)"
cat -v out/ch09/traceback_typo.color.txt
python3 -W error -c 'import warnings; warnings.warn("x")' \
    > out/ch09/warning_as_error.txt 2>&1 || true
cat out/ch09/warning_as_error.txt

# pdb driven by stdin.
bash lab/ch09/pdb_session.sh > out/ch09/pdb_session.txt
echo "pdb_session: $(wc -l < out/ch09/pdb_session.txt) lines"

# PEP 768: python -m pdb -p PID. The attach may be denied (ptrace);
# either way the outcome is recorded and the script goes on.
echo "ptrace_scope: $(cat /proc/sys/kernel/yama/ptrace_scope 2>&1)" \
    > out/ch09/pdb_attach.txt
python3 -c 'import time
while True:
    time.sleep(0.1)' &
target=$!
sleep 1
set +e
printf '%s\n' where continue \
    | timeout 20 python3 -m pdb -p "$target" >> out/ch09/pdb_attach.txt 2>&1
echo "pdb -p exit status: $?" >> out/ch09/pdb_attach.txt
set -e
kill "$target" 2>/dev/null || true
wait "$target" 2>/dev/null || true
cat out/ch09/pdb_attach.txt

# The same mechanism, allowed: a parent may attach to its own child.
python3 lab/ch09/helpers/remote_exec_demo.py \
    | tee out/ch09/remote_exec_demo.txt

#!/usr/bin/env bash
# Run subsets of the real test suite to show one pytest feature each.
# Every section prints the command first, so the output reads on its
# own. Expected failures are part of the demos: set +e where needed.
set -uo pipefail

# The nix pytest script runs its own interpreter, which does not see the
# editable install in .venv: go through the venv python instead.
pytest() {
    python3 -m pytest "$@"
}

out=$PWD/out/ch10
mkdir -p "$out"
log="$out/pytest_features.txt"
: > "$log"

show() {
    local line="\$" arg
    for arg in "$@"; do
        case $arg in
            *[[:space:]\(\)]*) line+=" '$arg'" ;;
            *) line+=" $arg" ;;
        esac
    done
    echo "$line" | tee -a "$log"
    "$@" 2>&1 | tee -a "$log"
    echo | tee -a "$log"
}

# What is there: node ids are file::function[param id].
show pytest --collect-only -q tests/test_markdown.py \
    -k test_strip_inline_syntax

# parametrize: one function, many cases; -v shows every id.
show pytest -vv -k "test_strip_inline_syntax and bold" \
    tests/test_markdown.py

# tmp_path: a fresh directory per test.
show pytest -vv tests/test_corpus.py -k "sorted_path or lazily"

# monkeypatch and capsys: the CLI test swaps CORPUS and reads stdout.
show pytest -vv tests/test_cli.py \
    -k "test_search_prints or test_stats"
show pytest -vv tests/test_log.py -k "stderr"

# pytest.raises(match=): the message is checked with re.search.
show pytest -vv tests/test_frontmatter.py -k "malformed and duplicate"

# Fixtures and scopes: S = session, F = function. The session fixtures
# are set up once, before the first test that asks for them.
show pytest --setup-show tests/test_search.py \
    -k "test_result_fields or test_no_match"

# Marks: -m selects, --strict-markers would reject an unknown one.
show pytest -m slow -vv
show pytest -m "not slow" --co -q tests/test_corpus.py

# xfail(strict=True): a known gap that fails today and must keep
# failing until somebody fixes it (then strict makes it an error).
show pytest -rx tests/test_markdown.py -k angle_brackets

# Slowest tests, and the hypothesis statistics of one property.
show pytest --durations=5 tests/test_properties.py
show pytest --hypothesis-show-statistics \
    tests/test_properties.py -k "inverts"

# A failing assert and --lf, in a scratch project so the repository
# tests stay green. its own pytest.ini keeps the repo's addopts out of it.
scratch=$out/scratch
rm -rf "$scratch"
mkdir -p "$scratch"
echo "[pytest]" > "$scratch/pytest.ini"
cat > "$scratch/test_scratch.py" <<'PY'
def test_passes():
    assert 1 + 1 == 2


def test_fails():
    got = [7, 6]
    # BAD: the expected order is wrong on purpose
    # error: AssertionError: assert [7, 6] == [6, 7]
    assert got == [6, 7]
PY
cd "$scratch"
show pytest -q
show pytest -q --lf
exit 0

#!/usr/bin/env bash
# Experiments that run pytest itself: feature subsets, coverage and
# the pytest-benchmark run.
set -euo pipefail

# The nix pytest script runs its own interpreter, which does not see the
# editable install in .venv: go through the venv python instead.
pytest() {
    python3 -m pytest "$@"
}

mkdir -p out/ch10

bash lab/ch10/pytest_features.sh > /dev/null
echo "pytest_features: $(wc -l < out/ch10/pytest_features.txt) lines"

# Whole suite with coverage; the report is the figure in the post.
pytest --cov=sift --cov-report=term-missing \
    | tee out/ch10/coverage.txt

# pytest-benchmark: collected only through this explicit path.
pytest lab/ch10/bench_tokenize.py --benchmark-only \
    --benchmark-columns=min,median,max,rounds \
    --benchmark-max-time=0.2 --benchmark-disable-gc \
    --benchmark-json=out/ch10/bench_tokenize.json \
    | tee out/ch10/bench_tokenize.txt

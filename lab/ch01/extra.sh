# 朴素搜索对比 grep：同一个词，同一批文件。
set -euo pipefail

mkdir -p out/ch01
hyperfine --warmup 3 --runs 20 \
    --export-json out/ch01/naive_vs_grep.json \
    'python3 -m sift search kalman' \
    'grep -rci kalman corpus/posts' \
    | tee out/ch01/naive_vs_grep.txt
python3 - <<'PY'
import json

with open("out/ch01/naive_vs_grep.json") as f:
    runs = json.load(f)["results"]
sift, grep = (r["mean"] for r in runs)
print(f"python/grep ratio: {sift / grep:.1f}x")
PY

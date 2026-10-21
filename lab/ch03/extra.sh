#!/usr/bin/env bash
# 同一个脚本用两个不同的 PYTHONHASHSEED 跑两次，对比 str 的 hash 与 set 顺序。
set -euo pipefail

mkdir -p out/ch03
for seed in 1 2; do
    PYTHONHASHSEED=$seed python3 lab/ch03/dict_order_and_hash.py \
        > "out/ch03/dict_order_and_hash.seed$seed.txt"
done
diff out/ch03/dict_order_and_hash.seed1.txt \
    out/ch03/dict_order_and_hash.seed2.txt || true

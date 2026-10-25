#!/usr/bin/env bash
# load_compare.sh: lab/ch17/load.py against FastAPI on uvicorn and
# against the hand-written asyncio server, same parameters as ch17
# (100 clients x 20 requests, one connection per request), rounds
# alternating. compare_bodies: the same requests to both servers; the
# status and the JSON must be identical (took_ms differs by nature).
# The servers run on an index of the corpus built in a temp dir. The
# numbers differ from run to run; the layout of the output does not.
set -euo pipefail

mkdir -p out/ch18
work=$(mktemp -d)
pids=()
cleanup() {
    for pid in "${pids[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    rm -rf "$work"
}
trap cleanup EXIT
export SIFT_INDEX="$work/idx"
sift index --corpus corpus/posts > "$work/index.txt"

# wait_listening LOG PID: wait for the "listening on URL" line of LOG.
wait_listening() {
    local log=$1 pid=$2
    for _ in $(seq 100); do
        if grep -q '^listening on ' "$log"; then
            return 0
        fi
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
    done
    echo "server did not start:" >&2
    cat "$log" "$log.err" >&2
    return 1
}

# start_server NAME CMD...: run CMD as a child of this script; sets
# server_pid and server_port.
start_server() {
    local name=$1
    shift
    "$@" > "$work/$name.log" 2> "$work/$name.log.err" &
    server_pid=$!
    pids+=("$server_pid")
    wait_listening "$work/$name.log" "$server_pid"
    server_port=$(sed -n 's/^listening on .*:\([0-9]*\)$/\1/p' \
        "$work/$name.log")
}

# --- load_compare.sh ------------------------------------------------
# A search costs 5 to 20 ms with limit=1, all of it CPU under the GIL.
# /health costs nothing: it measures only how each server handles 100
# connections at once.
#
# One cap is lifted for both servers: the default of 32 pending
# searches would answer 503 to most of the 100 clients, so they run
# with --max-pending 128. The cap on open connections is 256 for both
# (uvicorn's limit_concurrency, the MAX_CONNECTIONS of the raw server),
# above the 100 clients, so it stays.
start_server fastapi python3 -m sift serve --port 0 --quiet \
    --max-pending 128
fastapi_pid=$server_pid fastapi_port=$server_port
start_server raw python3 -m sift serve --raw --port 0 --quiet \
    --max-pending 128
raw_pid=$server_pid raw_port=$server_port

{
    python3 - "$fastapi_port" "$raw_port" <<'PY'
import json
import sys
import urllib.error
import urllib.request

PATHS = [
    "/health",
    "/search?q=rust&limit=1",
    "/search?q=kalman+filter&limit=2",
    "/search?q=%22device+tree%22&limit=1",
    "/search?q=%E5%A5%87%E5%BC%82%E5%80%BC&limit=1",
    "/search?q=owner*&limit=1",
    "/docs/5",
    "/docs/0005",
    "/docs/99999",
    "/docs/abc",
    "/search",
    "/search?q=",
    "/search?q=rust&limit=0",
    "/search?q=rust&limit=101",
    "/search?q=rust&limit=x",
    "/search?q=rust&limit=",
    "/search?q=(rust",
    "/search?q=rust+AND",
    "/nope",
]


def ask(port: str, path: str) -> tuple[int, dict[str, object]]:
    """Return the status and the JSON body, without took_ms."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    body = json.loads(raw)
    body.pop("took_ms", None)
    return status, body


def main() -> None:
    """Compare the two servers on every path."""
    fastapi_port, raw_port = sys.argv[1:]
    same = 0
    for path in PATHS:
        fastapi = ask(fastapi_port, path)
        raw = ask(raw_port, path)
        verdict = "identical" if fastapi == raw else "DIFFERENT"
        same += fastapi == raw
        print(f"  {verdict:<9} {fastapi[0]} {path}")
        if fastapi != raw:
            print("    fastapi:", fastapi)
            print("    raw    :", raw)
    print(f"{same} of {len(PATHS)} identical (status and JSON, no took_ms)")
    sys.exit(0 if same == len(PATHS) else 1)


main()
PY
} | tee out/ch18/compare_bodies.txt

# compare ROUNDS TITLE LOAD_ARGS...: warm up, then alternate the two
# servers for ROUNDS rounds.
compare() {
    local rounds=$1 title=$2
    shift 2
    local args=(--clients 100 --requests 20 "$@")
    echo "### $title"
    echo "$ python3 lab/ch17/load.py --port <port> ${args[*]}"
    for kind in fastapi raw; do
        port_var=${kind}_port
        python3 lab/ch17/load.py --port "${!port_var}" --clients 10 \
            --requests 2 "$@" > /dev/null
    done
    for round in $(seq "$rounds"); do
        for kind in fastapi raw; do
            port_var=${kind}_port
            echo
            echo "== round $round: $kind"
            python3 lab/ch17/load.py --port "${!port_var}" "${args[@]}" \
                | tee "$work/$kind.$round"
        done
    done
    echo
    echo "summary of $title"
    for kind in fastapi raw; do
        for round in $(seq "$rounds"); do
            awk -v kind="$kind" -v round="$round" '
                $1 == "req/s" {rps = $2}
                $1 == "p50" {p50 = $2}
                $1 == "p99" {p99 = $2}
                END {printf "%-9s round %d  %8.1f req/s  p50 %7.1f ms  " \
                            "p99 %7.1f ms\n", kind, round, rps, p50, p99}
            ' "$work/$kind.$round"
        done
    done
}

{
    compare 2 "GET /search?q=...&limit=1" --limit 1
    echo
    compare 3 "GET /health" --target /health
} | tee out/ch18/load_compare.txt

# SIGTERM must end both servers with status 0.
kill -TERM "$fastapi_pid" "$raw_pid"
wait "$fastapi_pid"
wait "$raw_pid"
pids=()

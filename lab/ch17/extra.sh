#!/usr/bin/env bash
# asyncio_ps.sh: start `sift serve --raw` with two clients stuck in the
# middle of a request head, then run `python -m asyncio ps <pid>` and
# `python -m asyncio pstree <pid>` (3.14) against it.
# load_compare.sh: lab/ch17/load.py against the asyncio server and
# against ThreadingHTTPServer, same parameters, rounds alternating.
# The servers run on an index of the corpus built in a temp dir. The
# numbers differ from run to run; the layout of the output does not.
set -euo pipefail

mkdir -p out/ch17
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

# stop_server: SIGTERM must end the server with status 0.
stop_server() {
    kill -TERM "$server_pid"
    wait "$server_pid"
}

# --- asyncio_ps.sh --------------------------------------------------
# Yama (ptrace_scope=1) lets a process attach only to its descendants,
# and `python -m asyncio ps` attaches. A server started next to it, as
# its sibling, is refused. Here a subshell starts the server (its
# child) and then becomes the `asyncio` command with exec, so the
# attaching process is the parent of the server.
inspect_server() {
    local sub=$1
    (
        python3 -m sift serve --raw --port 0 --quiet \
            > "$work/ps.log" 2> "$work/ps.log.err" &
        echo $! > "$work/ps.pid"
        wait_listening "$work/ps.log" "$(cat "$work/ps.pid")"
        port=$(sed -n 's/^listening on .*:\([0-9]*\)$/\1/p' "$work/ps.log")
        # two clients that sent half a head and went quiet
        exec 3<> "/dev/tcp/127.0.0.1/$port"
        exec 4<> "/dev/tcp/127.0.0.1/$port"
        printf 'GET /health HTTP/1.1\r\nHo' >&3
        printf 'GET /search?q=rust HTTP/1.1\r\n' >&4
        sleep 0.3
        echo "$ python3 -m asyncio $sub $(cat "$work/ps.pid")"
        exec python3 -m asyncio "$sub" "$(cat "$work/ps.pid")"
    ) 2>&1
    pid=$(cat "$work/ps.pid")
    kill -TERM "$pid"
    for _ in $(seq 100); do
        kill -0 "$pid" 2>/dev/null || return 0
        sleep 0.1
    done
    echo "server $pid did not stop after SIGTERM" >&2
    return 1
}

{
    echo "ptrace_scope: $(cat /proc/sys/kernel/yama/ptrace_scope \
        2> /dev/null || echo 'no Yama')"
    echo
    echo "# attach from a sibling process (refused when scope is 1)"
    python3 -m sift serve --raw --port 0 --quiet \
        > "$work/sib.log" 2> "$work/sib.log.err" &
    sibling=$!
    pids+=("$sibling")
    wait_listening "$work/sib.log" "$sibling"
    echo "$ python3 -m asyncio ps $sibling"
    if python3 -m asyncio ps "$sibling" 2>&1; then
        echo "(attached: ptrace_scope allows siblings here)"
    else
        echo "(exit status $?)"
    fi
    kill -TERM "$sibling"
    wait "$sibling"
    echo
    echo "# attach from the parent of the server"
    inspect_server ps
} | tee out/ch17/asyncio_ps.txt
inspect_server pstree | tee out/ch17/asyncio_pstree.txt

# --- load_compare.sh ------------------------------------------------
# A search costs 5 to 20 ms with limit=1 (the snippets of ten hits cost
# ten times more), all of it CPU under the GIL. /health costs nothing:
# it measures only how each server handles 100 connections at once.
#
# The default cap of 32 pending searches would answer 503 to most of
# the 100 clients; lift it, as the threaded server has no cap
start_server raw python3 -m sift serve --raw --port 0 --quiet \
    --max-pending 128
raw_pid=$server_pid raw_port=$server_port
start_server threaded python3 lab/ch17/threaded_http_server.py --port 0
threaded_pid=$server_pid threaded_port=$server_port

# compare_bodies.sh: the same 15 requests to both servers; status and
# JSON must be identical (took_ms differs by nature). The threaded
# server has no /docs route, so /docs is not part of it.
{
    python3 - "$raw_port" "$threaded_port" <<'PY'
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
    raw_port, threaded_port = sys.argv[1:]
    same = 0
    for path in PATHS:
        raw = ask(raw_port, path)
        threaded = ask(threaded_port, path)
        verdict = "identical" if raw == threaded else "DIFFERENT"
        same += raw == threaded
        print(f"  {verdict:<9} {raw[0]} {path}")
        if raw != threaded:
            print("    raw     :", raw)
            print("    threaded:", threaded)
    print(f"{same} of {len(PATHS)} identical (status and JSON, no took_ms)")
    sys.exit(0 if same == len(PATHS) else 1)


main()
PY
} | tee out/ch17/compare_bodies.txt

# compare ROUNDS TITLE LOAD_ARGS...: warm up, then alternate the two
# servers for ROUNDS rounds.
compare() {
    local rounds=$1 title=$2
    shift 2
    local args=(--clients 100 --requests 20 "$@")
    echo "### $title"
    echo "$ python3 lab/ch17/load.py --port <port> ${args[*]}"
    for kind in raw threaded; do
        port_var=${kind}_port
        python3 lab/ch17/load.py --port "${!port_var}" --clients 10 \
            --requests 2 "$@" > /dev/null
    done
    for round in $(seq "$rounds"); do
        for kind in raw threaded; do
            port_var=${kind}_port
            echo
            echo "== round $round: $kind"
            python3 lab/ch17/load.py --port "${!port_var}" "${args[@]}" \
                | tee "$work/$kind.$round"
        done
    done
    echo
    echo "summary of $title"
    for kind in raw threaded; do
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
} | tee out/ch17/load_compare.txt

kill -TERM "$raw_pid" "$threaded_pid"
wait "$raw_pid" "$threaded_pid"
pids=()

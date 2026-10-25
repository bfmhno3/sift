"""Send concurrent GET requests; report req/s and latency.

Each client opens a connection per request, one after the other, and
asks the server to close it (``Connection: close``: a server that keeps
connections alive, like uvicorn, would otherwise hold each one open
until its keep-alive timeout, and the read would wait for it). The
paths are the queries of --queries as /search?q=... (with &limit=N if
--limit is given), or the single path of --target.

--port N targets a server on localhost. Without it the script starts
a stub server that answers {} at once in this process. Generator and
stub then share one event loop, so the number is a floor for the
generator, not a ceiling for servers: a stub in its own process
answers faster.
"""

import argparse
import asyncio
import math
import time
from pathlib import Path
from urllib.parse import quote


async def fetch(host: str, port: int, target: str) -> int:
    """Open a connection, send one GET, return the status code."""
    reader, writer = await asyncio.open_connection(host, port)
    request = (
        f"GET {target} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
    )
    writer.write(request.encode())
    await writer.drain()
    answer = await reader.read()  # the server closes after one answer
    writer.close()
    await writer.wait_closed()
    return int(answer.split(b" ", 2)[1])


async def client(
    host: str,
    port: int,
    targets: list[str],
    requests: int,
    offset: int,
    latencies: list[float],
    errors: list[str],
) -> None:
    """Send requests one after the other, timing each."""
    for i in range(requests):
        target = targets[(offset + i) % len(targets)]
        start = time.perf_counter()
        try:
            status = await fetch(host, port, target)
        except OSError as error:
            errors.append(f"{target}: {error!r}")
            continue
        latencies.append(time.perf_counter() - start)
        if status != 200:
            errors.append(f"{target}: status {status}")


def percentile(sorted_values: list[float], percent: float) -> float:
    """Return the nearest-rank percentile of a sorted list."""
    rank = max(1, math.ceil(percent / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


async def run(
    host: str, port: int, targets: list[str], clients: int, requests: int
) -> list[str]:
    """Run all clients at once; print the numbers; return errors."""
    latencies: list[float] = []
    errors: list[str] = []
    start = time.perf_counter()
    async with asyncio.TaskGroup() as group:
        for n in range(clients):
            group.create_task(
                client(host, port, targets, requests, n, latencies, errors)
            )
    wall = time.perf_counter() - start
    latencies.sort()
    done = len(latencies)
    print(f"{clients} clients x {requests} requests, {done} answered")
    print(f"wall   {wall:8.3f} s")
    print(f"req/s  {done / wall:8.1f}")
    if latencies:
        print(f"p50    {percentile(latencies, 50) * 1000:8.1f} ms")
        print(f"p99    {percentile(latencies, 99) * 1000:8.1f} ms")
        print(f"max    {latencies[-1] * 1000:8.1f} ms")
    print(f"errors {len(errors):8d}")
    return errors


async def stub(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """Answer any request with an empty JSON object."""
    await reader.readuntil(b"\r\n\r\n")
    writer.write(
        b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}"
    )
    await writer.drain()
    writer.close()


async def amain(args: argparse.Namespace) -> list[str]:
    """Load the server on --port, or the stub if there is none."""
    if args.target:
        targets = [args.target]
    else:
        lines = Path(args.queries).read_text(encoding="utf-8").splitlines()
        extra = f"&limit={args.limit}" if args.limit else ""
        targets = [
            f"/search?q={quote(line)}{extra}" for line in lines if line.strip()
        ]
    if args.port is not None:
        return await run(
            args.host, args.port, targets, args.clients, args.requests
        )
    print("no --port: loading a stub server in this process")
    server = await asyncio.start_server(stub, args.host, 0, backlog=1024)
    port = server.sockets[0].getsockname()[1]
    async with server:
        return await run(args.host, port, targets, args.clients, args.requests)


def main() -> None:
    """Parse the command line, load, exit 1 if any request failed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--clients", type=int, default=100)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--queries", default="bench/queries.txt")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--target", help="one fixed path, e.g. /health")
    args = parser.parse_args()
    errors = asyncio.run(amain(args))
    for line in errors[:5]:
        print("error:", line)
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()

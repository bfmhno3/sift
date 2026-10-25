"""httpx: timeouts, connection pooling and 50 concurrent requests.

It starts ``sift serve`` (FastAPI on uvicorn, which keeps connections
alive) over an index in a temp dir and measures. The default cap of 32
pending searches would answer 503 to some of the 50 searches at once,
so the server runs with --max-pending 64:

1. 100 GET /health, each with a client of its own (a new connection
   every time) against one shared client (the pool reuses one);
2. 50 searches at once with ``AsyncSiftClient`` (a pool of up to 100
   connections), then with a plain ``httpx.AsyncClient`` limited to 5:
   the other 45 requests wait for a free connection.
"""

import asyncio
import os
import subprocess
import sys
import tempfile
import time

import httpx

from sift.client import AsyncSiftClient, SiftClient

COUNT = 100


def one_client_each(base: str) -> float:
    """Return seconds for COUNT requests, a new Client every time."""
    start = time.perf_counter()
    for _ in range(COUNT):
        with httpx.Client(base_url=base) as client:
            client.get("/health").raise_for_status()
    return time.perf_counter() - start


def shared_client(base: str) -> float:
    """Return seconds for COUNT requests over one pooled Client."""
    start = time.perf_counter()
    with SiftClient(base) as client:
        for _ in range(COUNT):
            client.health()
    return time.perf_counter() - start


async def fifty_at_once(base: str) -> None:
    """Search 50 times at once, over a pool of 100 and of 5."""
    words = ["rust", "kalman", "kernel", "device tree", "async"]
    async with AsyncSiftClient(base) as client:
        start = time.perf_counter()
        results = await asyncio.gather(
            *(client.search(words[i % 5], limit=1) for i in range(50))
        )
        wall = time.perf_counter() - start
    print(f"50 searches, pool of 100: {wall:.2f} s")
    print("totals:", sorted({r.total for r in results}))
    limits = httpx.Limits(max_connections=5)
    async with httpx.AsyncClient(base_url=base, limits=limits) as http:
        start = time.perf_counter()
        answers = await asyncio.gather(
            *(
                http.get("/search", params={"q": words[i % 5], "limit": 1})
                for i in range(50)
            )
        )
        wall = time.perf_counter() - start
    print(f"50 searches, pool of 5:   {wall:.2f} s")
    print("statuses:", {a.status_code for a in answers})


def main() -> None:
    """Start the server, measure, stop it."""
    with tempfile.TemporaryDirectory() as index:
        env = os.environ | {"SIFT_INDEX": index}
        subprocess.run(
            [sys.executable, "-m", "sift", "index"],
            env=env,
            check=True,
            capture_output=True,
        )
        server = subprocess.Popen(
            [sys.executable, "-m", "sift", "serve", "--port", "0"]
            + ["--quiet", "--max-pending", "64"],
            env=env,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert server.stdout is not None
            line = server.stdout.readline().strip()
            base = line.removeprefix("listening on ")
            print("server:", base)
            print("timeout default:", httpx.Client().timeout)
            each = one_client_each(base)
            shared = shared_client(base)
            print(f"{COUNT} requests, a client each: {each * 1000:7.1f} ms")
            print(f"{COUNT} requests, one client:    {shared * 1000:7.1f} ms")
            asyncio.run(fifty_at_once(base))
        finally:
            server.terminate()
            server.wait()


if __name__ == "__main__":
    main()

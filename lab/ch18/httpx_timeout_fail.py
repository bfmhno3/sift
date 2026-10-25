"""Let httpx time out on a deliberately slow local endpoint.

A tiny asyncio server runs in this script: ``/fast`` answers at once,
``/slow`` waits 2 s before it sends a byte. The client allows 0.3 s
for a read, so the second request raises httpx.ReadTimeout, which this
script does not catch: it exits with status 1 and the traceback.
"""

import asyncio

import httpx

DELAY = 2.0  # seconds /slow waits before it answers


async def handle(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """Answer one request; /slow takes DELAY seconds to start."""
    head = await reader.readuntil(b"\r\n\r\n")
    if head.startswith(b"GET /slow "):
        await asyncio.sleep(DELAY)
    body = b'{"ok": true}'
    writer.write(
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        b"Content-Length: %d\r\nConnection: close\r\n\r\n%b"
        % (len(body), body)
    )
    await writer.drain()
    writer.close()


async def main() -> None:
    """Ask /fast, then /slow with a read timeout of 0.3 s."""
    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    timeout = httpx.Timeout(5.0, read=0.3)
    print("timeout:", timeout)
    async with server, httpx.AsyncClient(timeout=timeout) as client:
        base = f"http://127.0.0.1:{port}"
        fast = await client.get(f"{base}/fast")
        print("/fast ->", fast.status_code, fast.json())
        # error: httpx.ReadTimeout, after 0.3 s of silence
        slow = await client.get(f"{base}/slow")
        print("unreachable:", slow.status_code)


if __name__ == "__main__":
    asyncio.run(main())

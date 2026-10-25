"""Ask the raw server with urllib.request from the standard library.

It starts ``sift serve --raw`` on a free port over an index in a temp
dir, then sends four requests. urllib needs no install, but it decodes
nothing for you: you build the URL, read the bytes, parse the JSON
and turn a 4xx into an exception yourself.
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


def get(url: str) -> tuple[int, dict[str, object]]:
    """Return the status and the JSON object of a GET."""
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:  # 4xx and 5xx raise
        with error:
            return error.code, json.load(error)


def show(base: str, path: str) -> None:
    """Print the answer to one GET."""
    status, body = get(base + path)
    print(f"GET {path} -> {status}")
    hits = body.get("hits")
    if isinstance(hits, list):
        for hit in hits:
            print(f"  {hit['score']:.3f}  {hit['title']}")
    else:
        print("  ", body)


def main() -> None:
    """Start the server, ask it, stop it."""
    with tempfile.TemporaryDirectory() as index:
        env = os.environ | {"SIFT_INDEX": index}
        subprocess.run(
            [sys.executable, "-m", "sift", "index"],
            env=env,
            check=True,
            capture_output=True,
        )
        server = subprocess.Popen(
            [sys.executable, "-m", "sift", "serve", "--raw"]
            + ["--port", "0", "--quiet"],
            env=env,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert server.stdout is not None
            line = server.stdout.readline().strip()
            base = line.removeprefix("listening on ")
            print("server:", base)
            query = urllib.parse.urlencode({"q": "rust lifetime", "limit": 2})
            show(base, "/health")
            show(base, f"/search?{query}")
            show(base, "/search?q=(rust")
            request = urllib.request.Request(base + "/health", method="POST")
            try:
                urllib.request.urlopen(request, timeout=5)
            except urllib.error.HTTPError as error:
                print(f"POST /health -> {error.code}, Allow:", end=" ")
                print(error.headers["Allow"])
        finally:
            server.terminate()
            server.wait()


if __name__ == "__main__":
    main()

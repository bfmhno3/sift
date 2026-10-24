"""Serve /search with http.server.ThreadingHTTPServer, for comparison.

Without arguments it starts on a free port, asks two questions and
stops. With --port N (0 for any free port) it serves until SIGTERM
and prints the URL, like ``sift serve --raw``. It answers /search and
/health with the same JSON as the asyncio server and logs nothing.
"""

import argparse
import contextlib
import io
import json
import os
import signal
import tempfile
import threading
import urllib.request
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from sift import cli
from sift.analysis import build_pipeline
from sift.config import Config, load_config
from sift.errors import ConfigError, QuerySyntaxError
from sift.search import Searcher
from sift.server.raw import search_payload
from sift.storage.store import SEGMENT, open_index


class SiftHTTPServer(ThreadingHTTPServer):
    """One thread per connection, sharing one Searcher and a lock."""

    daemon_threads = True
    request_queue_size = 128  # the default 5 drops a burst of clients

    def __init__(
        self, address: tuple[str, int], searcher: Searcher, config: Config
    ) -> None:
        """Bind address; keep what the handler threads share."""
        super().__init__(address, Handler)
        self.searcher = searcher
        self.config = config
        self.lock = threading.Lock()  # Searcher is not thread-safe


class Handler(BaseHTTPRequestHandler):
    """Answer GET /search?q=... and GET /health."""

    server: SiftHTTPServer

    def reply(self, status: int, payload: object) -> None:
        """Send payload as JSON; HTTP/1.0 closes the connection."""
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Route the request."""
        url = urlsplit(self.path)
        if url.path == "/health":
            docs = self.server.searcher.index.n_docs
            self.reply(200, {"status": "ok", "docs": docs})
        elif url.path == "/search":
            params = parse_qs(url.query)
            self.search(params.get("q", [""])[0], params.get("limit", [""])[0])
        else:
            self.reply(404, {"error": f"no route for {url.path}"})

    def search(self, query: str, limit_text: str) -> None:
        """Run the query in this thread, one search at a time."""
        if not query.strip():
            self.reply(400, {"error": "missing query parameter q"})
            return
        try:
            limit = (
                Config.limit.validate(int(limit_text))
                if limit_text
                else self.server.config.limit
            )
        except ConfigError, ValueError:
            self.reply(400, {"error": "bad limit"})
            return
        try:
            with self.server.lock:
                result = self.server.searcher.search(query, limit)
        except QuerySyntaxError as error:
            self.reply(400, {"error": str(error)})
            return
        self.reply(200, search_payload(result))

    def log_message(self, format: str, *args: object) -> None:
        """Log nothing: the comparison measures the server."""


def ensure_index(stack: ExitStack) -> None:
    """Index the corpus into a temp dir if there is no index yet."""
    if (cli.index_dir(load_config()) / SEGMENT).exists():
        return
    directory = stack.enter_context(tempfile.TemporaryDirectory())
    os.environ["SIFT_INDEX"] = directory
    with contextlib.redirect_stdout(io.StringIO()):
        cli.main(["index"])


def self_test(server: SiftHTTPServer) -> None:
    """Ask the server two questions from this process."""
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for path in ("/health", "/search?q=rust+lifetime"):
            with urllib.request.urlopen(base + path) as response:
                body = json.load(response)
            keys = ", ".join(body)
            print(f"GET {path} -> {response.status}: {keys}")
    finally:
        server.shutdown()
        thread.join()


def stop(signum: int, frame: object) -> None:
    """Turn SIGTERM into KeyboardInterrupt so serve_forever ends."""
    raise KeyboardInterrupt


def main() -> None:
    """Self-test, or serve on --port until SIGTERM."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    with ExitStack() as stack:
        if args.port is None:
            ensure_index(stack)
        config = load_config()
        index = stack.enter_context(open_index(cli.index_dir(config)))
        searcher = Searcher(
            index,
            k1=config.k1,
            b=config.b,
            pipeline=build_pipeline(index.pipeline_names),
        )
        server = stack.enter_context(
            SiftHTTPServer(("127.0.0.1", args.port or 0), searcher, config)
        )
        if args.port is None:
            self_test(server)
            return
        signal.signal(signal.SIGTERM, stop)
        print(
            f"listening on http://127.0.0.1:{server.server_port}", flush=True
        )
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()


if __name__ == "__main__":
    main()

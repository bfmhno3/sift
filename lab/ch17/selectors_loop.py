"""Serve the echo protocol from one thread with a selectors loop."""

import selectors
import socket
import threading
from collections.abc import Callable

Callback = Callable[[socket.socket], None]


class Loop:
    """Wait for readable sockets and call their callbacks."""

    def __init__(self) -> None:
        """Create the selector (epoll on Linux)."""
        self.selector = selectors.DefaultSelector()
        self.calls = 0

    def add_reader(self, sock: socket.socket, callback: Callback) -> None:
        """Call callback(sock) whenever sock is readable."""
        self.selector.register(sock, selectors.EVENT_READ, callback)

    def remove_reader(self, sock: socket.socket) -> None:
        """Stop watching sock."""
        self.selector.unregister(sock)

    def run_until(self, done: Callable[[], bool]) -> None:
        """Run callbacks as sockets become ready until done()."""
        while not done():
            for key, _ in self.selector.select(timeout=0.05):
                self.calls += 1
                key.data(key.fileobj)


def serve(loop: Loop, listener: socket.socket) -> None:
    """Accept clients and echo what they send, never blocking."""
    listener.setblocking(False)

    def on_client(conn: socket.socket) -> None:
        chunk = conn.recv(1024)
        if chunk:
            conn.send(chunk)  # fits the socket buffer: no write wait
        else:
            loop.remove_reader(conn)
            conn.close()

    def on_accept(sock: socket.socket) -> None:
        conn, _ = sock.accept()
        conn.setblocking(False)
        loop.add_reader(conn, on_client)

    loop.add_reader(listener, on_accept)


def client(port: int, name: str, results: dict[str, str]) -> None:
    """Send three lines, one at a time, and keep what comes back."""
    with socket.create_connection(("127.0.0.1", port)) as conn:
        got = []
        for i in range(3):
            conn.sendall(f"{name}-{i}".encode())
            got.append(conn.recv(1024).decode())
        results[name] = " ".join(got)


def main() -> None:
    """Serve five clients in the main thread, and say how."""
    loop = Loop()
    listener = socket.create_server(("127.0.0.1", 0))
    serve(loop, listener)
    port = listener.getsockname()[1]
    results: dict[str, str] = {}
    threads = [
        threading.Thread(target=client, args=(port, f"c{i}", results))
        for i in range(5)
    ]
    for thread in threads:
        thread.start()
    loop.run_until(lambda: len(results) == 5)
    for name in sorted(results):
        print(name, results[name])
    print("selector:", type(loop.selector).__name__)
    print("server thread:", threading.current_thread().name)
    print("callbacks run:", loop.calls)
    listener.close()


if __name__ == "__main__":
    main()

"""Serve an echo protocol with blocking sockets and threads."""

import socket
import threading
import time


def echo(conn: socket.socket) -> None:
    """Send back every chunk until the peer closes."""
    with conn:
        while chunk := conn.recv(1024):
            conn.sendall(chunk)


def accept_loop(listener: socket.socket, threaded: bool) -> None:
    """Accept connections; serve each in a new thread or inline."""
    while True:
        try:
            conn, _ = listener.accept()
        except OSError:
            return  # the listener was closed
        if threaded:
            threading.Thread(target=echo, args=(conn,), daemon=True).start()
        else:
            echo(conn)


def listen(threaded: bool) -> tuple[socket.socket, int]:
    """Start an echo server on a free port; return it and the port."""
    listener = socket.create_server(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    threading.Thread(
        target=accept_loop, args=(listener, threaded), daemon=True
    ).start()
    return listener, port


def ask(port: int, text: str, patience: float) -> str:
    """Connect, send text, wait patience seconds for the echo."""
    with socket.create_connection(("127.0.0.1", port)) as conn:
        conn.settimeout(patience)
        conn.sendall(text.encode())
        try:
            return conn.recv(1024).decode()
        except TimeoutError:
            return "<no answer>"


def main() -> None:
    """Show that a blocking server needs one thread per client."""
    print("-- one thread per client")
    listener, port = listen(threaded=True)
    # this client connects and then says nothing
    idle = socket.create_connection(("127.0.0.1", port))
    start = time.perf_counter()
    reply = ask(port, "hello", patience=1.0)
    took = time.perf_counter() - start
    print(f"idle client holds a thread; second client: {reply!r}")
    print(f"answered in under 0.2 s: {took < 0.2}")
    idle.close()
    listener.close()

    print("-- one thread for everyone")
    listener, port = listen(threaded=False)
    idle = socket.create_connection(("127.0.0.1", port))
    reply = ask(port, "hello", patience=0.3)
    print(f"idle client holds the only thread; second client: {reply!r}")
    idle.close()  # recv() returns b"", the server accepts the next one
    time.sleep(0.1)
    print("after the idle client left:", repr(ask(port, "hello", 1.0)))
    listener.close()


if __name__ == "__main__":
    main()

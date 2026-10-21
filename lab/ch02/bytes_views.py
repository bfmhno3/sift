"""bytes, bytearray and memoryview."""

import time


def main() -> None:
    """Show immutability, mutation and zero-copy slicing."""
    b = "所有权".encode()
    print(b, b[0], b[:3], b[:3].decode(), list(b[:3]))
    print(bytes([104, 105]), bytes(3), b"ab" * 2, b.hex())
    ba = bytearray(b"hello")
    ba[0] = ord("j")
    ba.extend(b"!!")
    print(ba, bytes(ba))
    try:
        b[0] = 1  # type: ignore[index]
    except TypeError as exc:
        print("TypeError:", exc)

    data = bytes(range(256)) * 4096
    view = memoryview(data)
    part = view[1000:2000]
    print(len(data), part.nbytes, part.obj is data, part[0], part[-1])
    copy = data[1000:2000]
    print(copy is data, type(copy).__name__, type(part).__name__)
    buf = bytearray(b"abcdef")
    mv = memoryview(buf)
    mv[1:3] = b"XY"
    print(buf)
    mv.release()

    n = 2000
    start = time.perf_counter_ns()
    for _ in range(n):
        _ = data[:-1]
    t_copy = time.perf_counter_ns() - start
    start = time.perf_counter_ns()
    for _ in range(n):
        _ = view[:-1]
    t_view = time.perf_counter_ns() - start
    print(f"slice {len(data)} bytes x{n}: copy {t_copy / 1e6:.2f} ms,")
    print(f"  memoryview {t_view / 1e6:.2f} ms, ratio {t_copy / t_view:.0f}")


if __name__ == "__main__":
    main()

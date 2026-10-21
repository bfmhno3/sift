"""Decode GBK bytes as UTF-8."""


def main() -> None:
    """Fail with UnicodeDecodeError."""
    data = "所有权".encode("gbk")
    print(data.hex(" "))
    # error: UnicodeDecodeError, the GBK bytes are not valid UTF-8
    print(data.decode("utf-8"))


if __name__ == "__main__":
    main()

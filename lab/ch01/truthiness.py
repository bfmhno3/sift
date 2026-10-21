"""Which values are falsy, and how a class can decide."""


class Empty:
    """An object that is falsy through __len__."""

    def __len__(self) -> int:
        return 0


class Flag:
    """An object that decides through __bool__."""

    def __init__(self, on: bool) -> None:
        self.on = on

    def __bool__(self) -> bool:
        return self.on


def main() -> None:
    """Print the truth value of common objects."""
    samples = [
        None,
        False,
        0,
        0.0,
        0j,
        "",
        b"",
        [],
        (),
        {},
        set(),
        range(0),
        "0",
        " ",
        [0],
        Empty(),
        Flag(False),
        Flag(True),
    ]
    for value in samples:
        print(f"{type(value).__name__:<8}{value!r:<36.34}{bool(value)}")
    print("[] == False:", [] == False)  # noqa: E712
    print("0 == False:", 0 == False)  # noqa: E712
    print("'' or 'default':", "" or "default")  # noqa: SIM222
    print("'x' and 'y':", "x" and "y")
    print("None or 0 or []:", None or 0 or [])


if __name__ == "__main__":
    main()

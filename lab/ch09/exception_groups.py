"""ExceptionGroup, except*, split and subgroup, and its limits."""


def fail_all() -> None:
    """Raise a group of three unrelated errors."""
    raise ExceptionGroup(
        "3 files failed",
        [
            ValueError("a.md: bad title"),
            ValueError("b.md: bad date"),
            KeyError("c.md"),
        ],
    )


def main() -> None:
    """Handle a group with except*, then take it apart by hand."""
    try:
        fail_all()
    except* ValueError as group:
        print("except* ValueError got:", repr(group))
        print("  members:", [str(e) for e in group.exceptions])
    except* KeyError as group:
        print("except* KeyError got:", repr(group))

    try:
        try:
            fail_all()
        except* ValueError:
            print("handled the ValueErrors, KeyError goes on")
    except ExceptionGroup as rest:
        print("left over:", repr(rest))

    group = ExceptionGroup("mixed", [OSError("disk"), ValueError("v")])
    match, rest = group.split(OSError)
    print("split match:", repr(match), "rest:", repr(rest))
    print("subgroup:", repr(group.subgroup(ValueError)))
    print("derive:", repr(group.derive([TypeError("t")])))

    nested = ExceptionGroup("outer", [ValueError(1), group])
    try:
        raise nested
    except* OSError as caught:
        print("nested except* OSError:", repr(caught))
    except* ValueError as caught:
        print("nested except* ValueError:", repr(caught))

    try:
        raise ValueError("single")
    except* ValueError as caught:
        print("a plain error is wrapped:", repr(caught))

    try:
        raise BaseExceptionGroup("with exit", [KeyboardInterrupt(), OSError()])
    except* KeyboardInterrupt as caught:
        print("BaseExceptionGroup member:", repr(caught))
    except* OSError:
        print("and the OSError")

    try:
        ExceptionGroup("empty", [])
    except ValueError as exc:
        # error: ValueError: second argument (exceptions) must be a
        # non-empty sequence
        print("empty group:", exc)

    try:
        ExceptionGroup("bad", [KeyboardInterrupt()])
    except TypeError as exc:
        # error: TypeError: Cannot nest BaseExceptions in an
        # ExceptionGroup
        print("base in group:", exc)

    source = (
        "try:\n    pass\n"
        "except* ValueError:\n    pass\n"
        "except TypeError:\n    pass\n"
    )
    try:
        compile(source, "<mixed>", "exec")
    except SyntaxError as exc:
        # error: SyntaxError: cannot have both 'except' and 'except*'
        # on the same 'try'
        print("mixing except and except*:", exc.msg)


if __name__ == "__main__":
    main()

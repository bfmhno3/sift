"""Source to bytecode: dis and the fields of a code object."""

import dis


def add_one(n: int) -> int:
    """Return n + 1."""
    total = n + 1
    return total


def main() -> None:
    """Disassemble add_one and compile a string by hand."""
    dis.dis(add_one)
    code = add_one.__code__
    print("co_name:", code.co_name)
    print("co_argcount:", code.co_argcount)
    print("co_varnames:", code.co_varnames)
    print("co_consts:", code.co_consts)
    print("co_stacksize:", code.co_stacksize)
    print("co_code bytes:", len(code.co_code))

    compiled = compile("x = 2 + 3\nprint(x * 10)", "<demo>", "exec")
    print("type:", type(compiled).__name__)
    print("co_consts:", compiled.co_consts)
    print("co_names:", compiled.co_names)
    exec(compiled)


if __name__ == "__main__":
    main()

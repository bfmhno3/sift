"""eval on input is code execution; ast.literal_eval is not."""

import ast


def main() -> None:
    """Show three ways eval runs more than the 'expression'."""
    print("-- an innocent expression")
    print(" ", eval("1 + 2"))
    print("-- but the input chooses what runs")
    attack = "__import__('sys').version_info.major"
    print(" ", attack, "->", eval(attack))
    print("-- emptying __builtins__ is not a sandbox")
    escape = "().__class__.__bases__[0].__subclasses__()"
    classes = eval(escape, {"__builtins__": {}})
    print("  reached object.__subclasses__():", len(classes) > 100)
    try:
        eval("__import__('os')", {"__builtins__": {}})
    except NameError as error:
        print("  the direct way is blocked:", error)
    print("-- ast.literal_eval accepts literals only")
    print(" ", ast.literal_eval("[1, 2.5, 'x', (None, True), {'k': -3}]"))
    for text in ("__import__('os')", "1 + 2 * 3", "[x for x in 'ab']"):
        try:
            ast.literal_eval(text)
        except ValueError as error:
            print(f"  {text!r} -> ValueError: {str(error)[:40]}...")
    print("-- only a number plus an imaginary one may be joined")
    print(" ", ast.literal_eval("1 + 2j"))


if __name__ == "__main__":
    main()

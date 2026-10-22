"""try, except, else, finally: which clause runs when, in order."""


def clauses(label: str, action: str) -> str:
    """Run one try statement and print each clause as it executes."""
    print(f"-- {label}")
    try:
        print("  try: start")
        if action == "value":
            raise ValueError("bad value")
        if action == "key":
            raise KeyError("missing")
        if action == "return":
            return "returned from try"
        print("  try: end")
    except ValueError as exc:
        print(f"  except ValueError: {exc}")
    else:
        print("  else: the try block raised nothing")
    finally:
        print("  finally: always runs")
    return "fell off the end"


def loop_with_finally() -> None:
    """Show that break and continue also run the finally clause."""
    print("-- finally inside a loop")
    for i in range(3):
        try:
            if i == 1:
                continue
            if i == 2:
                break
            print(f"  body {i}")
        finally:
            print(f"  finally {i}")


def finally_runs_before_return() -> int:
    """Show that the return value is computed before finally runs."""
    value = 1
    try:
        return value
    finally:
        value = 2
        print(f"  finally set value to {value}, return still gives 1")


def main() -> None:
    """Print the execution order of every clause combination."""
    print(clauses("no exception", "none"))
    print(clauses("exception caught by except", "value"))
    print(clauses("return inside try", "return"))
    try:
        clauses("exception no except matches", "key")
    except KeyError as exc:
        print(f"  KeyError {exc} left the function after finally")
    loop_with_finally()
    print("-- return value")
    print(f"  got {finally_runs_before_return()}")


if __name__ == "__main__":
    main()

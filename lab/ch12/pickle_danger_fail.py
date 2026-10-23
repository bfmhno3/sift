"""Loading a pickle can run code: the payload calls os.system.

The command is a harmless echo. Never call pickle.loads on bytes that
you did not write yourself: a pickle is a program for the unpickler.
"""

# error: RuntimeError: pickle.loads ran os.system and returned 0, not an index

import io
import os
import pickle
import pickletools
import sys


class Payload:
    """An object whose pickle is a call, not data."""

    def __reduce__(self) -> tuple:
        """Tell pickle to rebuild this object by calling os.system."""
        return (os.system, ("echo pwned",))


class SafeUnpickler(pickle.Unpickler):
    """Refuse to look up any global: only plain data may be loaded."""

    def find_class(self, module: str, name: str) -> object:
        """Reject every class and function."""
        raise pickle.UnpicklingError(f"forbidden global {module}.{name}")


def main() -> None:
    """Build the payload, read it safely, then load it for real."""
    payload = pickle.dumps(Payload())
    print("pickle bytes:", len(payload))
    print("--- the opcodes: STACK_GLOBAL imports os.system, REDUCE calls it")
    pickletools.dis(payload)

    print("--- a restricted Unpickler refuses")
    try:
        SafeUnpickler(io.BytesIO(payload)).load()
    except pickle.UnpicklingError as error:
        print("UnpicklingError:", error)

    print("--- pickle.loads runs the command")
    sys.stdout.flush()
    result = pickle.loads(payload)
    print("loads returned:", result, "(the exit status of the shell)")
    raise RuntimeError(
        f"pickle.loads ran os.system and returned {result}, not an index"
    )


if __name__ == "__main__":
    main()

"""__init_subclass__: a registry filled by the class statement."""

from typing import Any

REGISTRY: dict[str, type[Plugin]] = {}


class Plugin:
    """Base class; each subclass names itself in its class line."""

    name: str

    def __init_subclass__(cls, /, name: str, **kwargs: Any) -> None:
        """Run once per subclass, right after the class is built."""
        super().__init_subclass__(**kwargs)
        if name in REGISTRY:
            raise ValueError(f"name taken: {name!r}")
        cls.name = name
        REGISTRY[name] = cls
        print(f"  registered {cls.__name__} as {name!r}")


def main() -> None:
    """Define plugins, look them up, then break the rules."""
    print("defining:")

    class Upper(Plugin, name="upper"):
        """Upper-case the text."""

    class Lower(Plugin, name="lower"):
        """Lower-case the text."""

    print("REGISTRY:", {k: v.__name__ for k, v in REGISTRY.items()})
    print("Upper.name:", Upper.name, "| Lower.name:", Lower.name)
    for attempt in ("duplicate", "missing"):
        try:
            if attempt == "duplicate":

                class Again(Plugin, name="upper"):
                    """Same name as Upper."""

            else:

                class Nameless(Plugin):
                    """No name keyword."""

        except (ValueError, TypeError) as exc:
            print(f"{attempt}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()

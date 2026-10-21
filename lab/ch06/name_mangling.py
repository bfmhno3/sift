"""Single underscore, double underscore and name mangling."""


class Base:
    """Holds a private-ish helper and a mangled attribute."""

    def __init__(self) -> None:
        """Set one attribute of each flavor."""
        self.public = 1
        self._internal = 2  # convention only: "please do not touch"
        self.__secret = 3  # stored as _Base__secret

    def reveal(self) -> int:
        """Read the mangled attribute from inside the class."""
        return self.__secret


class Child(Base):
    """Defines its own __secret without clobbering Base's."""

    def __init__(self) -> None:
        """Set a __secret that lives under a different mangled name."""
        super().__init__()
        self.__secret = 99  # stored as _Child__secret

    def child_secret(self) -> int:
        """Read Child's own mangled attribute."""
        return self.__secret


def main() -> None:
    """Show where the names really live."""
    b = Base()
    print("vars(Base()):", vars(b))
    print("b._internal:", b._internal)
    try:
        print(b.__secret)
    except AttributeError as exc:
        print("b.__secret ->", exc)
    print("b._Base__secret:", b._Base__secret)

    c = Child()
    print("vars(Child()):", vars(c))
    print("reveal() still sees Base's:", c.reveal())
    print("child_secret():", c.child_secret())
    print(
        "dunder names are not mangled: __init__ in vars:",
        "__init__" in vars(Base),
    )


if __name__ == "__main__":
    main()

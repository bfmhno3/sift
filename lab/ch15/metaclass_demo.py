"""Metaclasses: class creation step by step, and the lighter hook."""

from typing import Any

EVENTS: list[str] = []


def say(text: str) -> None:
    """Remember an event; main() prints them after the import."""
    EVENTS.append(text)


class Namespace(dict[str, Any]):
    """The dict the class body runs in: it sees every assignment."""

    def __setitem__(self, key: str, value: Any) -> None:
        if not key.startswith("__"):
            say(f"body assigns {key}")
        super().__setitem__(key, value)


class Meta(type):
    """Log each step of class creation."""

    @classmethod
    def __prepare__(
        mcs, name: str, bases: tuple[type, ...], **kwargs: object
    ) -> Namespace:
        say(f"__prepare__({name!r})")
        return Namespace()

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: object,
    ) -> Meta:
        say(f"__new__({name!r}) builds the class object")
        return super().__new__(mcs, name, bases, dict(namespace))

    def __init__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: object,
    ) -> None:
        say(f"__init__({name!r}) initializes it")
        super().__init__(name, bases, namespace)

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        say(f"Meta.__call__ makes an instance of {cls.__name__}")
        return super().__call__(*args, **kwargs)


class Marker:
    """Show where __set_name__ and __init_subclass__ fall."""

    def __set_name__(self, owner: type, name: str) -> None:
        say(f"__set_name__({owner.__name__}.{name})")


class Base:
    def __init_subclass__(cls) -> None:
        say(f"__init_subclass__({cls.__name__})")


class Steps(Base, metaclass=Meta):
    """The order is the lesson."""

    first = 1
    marker = Marker()

    def method(self) -> None:
        pass


REGISTRY_META: dict[str, type] = {}


class RegistryMeta(type):
    """A registry as a metaclass."""

    def __init__(
        cls, name: str, bases: tuple[type, ...], ns: dict[str, Any]
    ) -> None:
        super().__init__(name, bases, ns)
        if bases:
            REGISTRY_META[name.lower()] = cls


class PluginBase(metaclass=RegistryMeta):
    """The root is not registered: it has no bases of its own."""


class PluginA(PluginBase):
    pass


class PluginB(PluginA):
    pass


REGISTRY_HOOK: dict[str, type] = {}


class Plugin:
    """The same registry with __init_subclass__: no metaclass."""

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        REGISTRY_HOOK[cls.__name__.lower()] = cls


class HookA(Plugin):
    pass


class HookB(HookA):
    pass


def main() -> None:
    """Print the creation order, then the two registries."""
    print("-- the class statement of Steps ran at import:")
    for event in EVENTS:
        print(" ", event)
    print("-- type(name, bases, ns) is what `class` calls")
    made = type("Made", (), {"x": 1, "double": lambda self: self.x * 2})
    print(" ", made, made().double(), type(made).__name__)
    print("-- instance creation goes through Meta.__call__")
    EVENTS.clear()
    Steps()
    print(" ", EVENTS)
    print("-- metaclass of everything")
    print(" ", type(int), type(type), type(Steps), Steps.__mro__[1])
    print("-- registry as a metaclass vs __init_subclass__")
    print(" ", sorted(REGISTRY_META))
    print(" ", sorted(REGISTRY_HOOK))


if __name__ == "__main__":
    main()

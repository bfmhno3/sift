"""__getattr__ and __setattr__: a proxy that logs every access."""

import copy
from typing import Any

from sift.config import Config


class Proxy:
    """Forward unknown attributes to a target and log them."""

    def __init__(self, target: object) -> None:
        # object.__setattr__ skips our own __setattr__ below
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "log", [])

    def __getattr__(self, name: str) -> Any:
        # only called when normal lookup failed
        target = self.__dict__.get("_target")
        if target is None:  # a half-built copy: no recursion
            raise AttributeError(name)
        self.log.append(f"get {name}")
        return getattr(target, name)

    def __setattr__(self, name: str, value: object) -> None:
        self.__dict__["log"].append(f"set {name}")
        setattr(self.__dict__["_target"], name, value)


class Naive:
    """The classic bug: __getattr__ reads self._target."""

    def __init__(self, target: object) -> None:
        self._target = target

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


class Lazy:
    """Compute an attribute once, then let the instance dict win."""

    def __init__(self) -> None:
        self.calls = 0

    def __getattr__(self, name: str) -> int:
        if name != "answer":
            raise AttributeError(name)
        self.calls += 1
        self.__dict__["answer"] = 42  # next read never gets here
        return 42


def main() -> None:
    """Exercise the proxy, the recursion trap and a lazy attribute."""
    config = Config()
    proxy = Proxy(config)
    print("limit  :", proxy.limit)
    proxy.limit = 25
    print("limit  :", config.limit)
    print("k1     :", proxy.k1)
    print("log    :", proxy.log)
    try:
        proxy.limit = 0
    except Exception as error:
        print("refused:", type(error).__name__, error)
    print("-- the trap: __getattr__ before __init__ has run")
    naive = Naive(config)
    print("naive.limit:", naive.limit)
    try:
        copy.copy(naive)
    except RecursionError:
        print("copy.copy(Naive) -> RecursionError")
    print("copy.copy(Proxy) ->", type(copy.copy(proxy)).__name__)
    print("-- lazy attribute")
    lazy = Lazy()
    print(lazy.answer, lazy.answer, lazy.answer, "calls:", lazy.calls)
    print("hasattr(lazy, 'other'):", hasattr(lazy, "other"))


if __name__ == "__main__":
    main()

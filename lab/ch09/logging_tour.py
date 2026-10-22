"""logging: hierarchy, levels, handlers, formatters and dictConfig."""

import io
import logging
import logging.config
import sys

from sift.log import setup_logging


class Expensive:
    """An object that counts how often it is turned into text."""

    calls = 0

    def __str__(self) -> str:
        """Count the call and return a fixed text."""
        Expensive.calls += 1
        return "expensive"


def main() -> None:
    """Tour the logging module with deterministic output."""
    print("-- hierarchy: names with dots form a tree")
    root = logging.getLogger()
    sift = logging.getLogger("sift")
    corpus = logging.getLogger("sift.corpus")
    print("  corpus.parent is sift:", corpus.parent is sift)
    print("  sift.parent is root:  ", sift.parent is root)
    print(
        "  getLogger is a singleton:",
        corpus is logging.getLogger("sift.corpus"),
    )
    print("  effective level of sift.corpus:", corpus.getEffectiveLevel())

    print("-- handler + formatter on the parent, records from the child")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        logging.Formatter("%(levelname)-7s %(name)s: %(message)s")
    )
    sift.addHandler(handler)
    sift.setLevel(logging.INFO)
    sift.propagate = False
    corpus.debug("dropped: below INFO")
    corpus.info("indexed %d files", 123)
    corpus.warning("skipping %s", "bad.md")
    corpus.error("unreadable: %s", "x.md")
    try:
        print(1 / 0)
    except ZeroDivisionError:
        corpus.exception("caught something")
    lines = stream.getvalue().splitlines()
    for line in lines[:4]:
        print("  " + line)
    print("  ... then the traceback:", lines[4], "|", lines[-1])

    print("-- levels")
    for name in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        print(f"  {name:8} = {logging.getLevelName(name)}")
    print("  isEnabledFor(DEBUG):", corpus.isEnabledFor(logging.DEBUG))

    print("-- lazy % formatting: no str() when the level is off")
    Expensive.calls = 0
    corpus.debug("value: %s", Expensive())
    print("  after debug (off), __str__ calls:", Expensive.calls)
    corpus.debug(f"value: {Expensive()}")
    print("  after f-string debug, __str__ calls:", Expensive.calls)
    corpus.info("value: %s", Expensive())
    print("  after info (on), __str__ calls:", Expensive.calls)

    print("-- filters and extra")

    class OnlyBad(logging.Filter):
        """Keep records whose message mentions 'bad'."""

        def filter(self, record: logging.LogRecord) -> bool:
            """Return True for the records to keep."""
            return "bad" in record.getMessage()

    other = io.StringIO()
    second = logging.StreamHandler(other)
    second.addFilter(OnlyBad())
    second.setFormatter(logging.Formatter("%(message)s [%(file)s]"))
    sift.addHandler(second)
    corpus.warning("bad front matter", extra={"file": "a.md"})
    corpus.warning("all good", extra={"file": "b.md"})
    print("  filtered handler saw:", other.getvalue().strip())
    sift.removeHandler(second)

    print("-- dictConfig")
    sift.removeHandler(handler)
    sift.propagate = True
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"short": {"format": "[%(levelname)s] %(message)s"}},
        "handlers": {
            "out": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "short",
            }
        },
        "loggers": {"sift": {"handlers": ["out"], "level": "DEBUG"}},
    }
    logging.config.dictConfig(config)
    logging.getLogger("sift.index").debug("hello from dictConfig")

    print("-- sift.log.setup_logging")
    setup_logging("INFO")
    setup_logging("INFO")
    print("  handlers after two calls:", len(sift.handlers))
    stderr_handler = sift.handlers[0]
    print(
        "  the handler writes to stderr:",
        isinstance(stderr_handler, logging.StreamHandler)
        and stderr_handler.stream is sys.stderr,
    )
    try:
        setup_logging("LOUD")
    except ValueError as exc:
        # error: ValueError: unknown log level: 'LOUD'
        print("  bad level:", exc)


if __name__ == "__main__":
    main()

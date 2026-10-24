"""Carry a request id across tasks and threads with contextvars."""

import asyncio
import contextvars
import logging

request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIdFilter(logging.Filter):
    """Stamp every log record with the current request id."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add record.request_id; keep the record."""
        record.request_id = request_id.get()
        return True


def blocking_step() -> str:
    """Run in a worker thread: the context was copied there."""
    return f"thread sees {request_id.get()}"


async def child() -> str:
    """Read the id set by whoever created this task."""
    await asyncio.sleep(0)
    return f"child sees {request_id.get()}"


async def handle(name: str) -> list[str]:
    """Set the id, then call a task, a thread and a log line."""
    request_id.set(name)
    logging.getLogger("demo").info("handling")
    lines = [await asyncio.create_task(child())]
    lines.append(await asyncio.to_thread(blocking_step))
    lines.append(f"{name} still has {request_id.get()}")
    return lines


async def writer() -> str:
    """Set the id inside a task: the parent never sees it."""
    request_id.set("set-in-task")
    return request_id.get()


async def main() -> None:
    """Run two requests at once; they never see each other's id."""
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(logging.Formatter("  [%(request_id)s] %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    logging.getLogger("demo").info("before any request")
    first, second = await asyncio.gather(handle("req-1"), handle("req-2"))
    for line in first + second:
        print(" ", line)
    print("-- a task works on a copy of the context")
    print("  task set:", await asyncio.create_task(writer()))
    print("  parent has:", request_id.get())
    token = request_id.set("outer")
    request_id.reset(token)
    print("  after reset(token):", request_id.get())


if __name__ == "__main__":
    asyncio.run(main())

"""Run executors.py on the free-threaded build (python3.14t)."""

import asyncio

from executors import main

if __name__ == "__main__":
    asyncio.run(main())

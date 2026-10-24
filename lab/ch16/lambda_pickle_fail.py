"""Submit a lambda to a process pool: it cannot be pickled."""

from concurrent.futures import ProcessPoolExecutor


def main() -> None:
    """Ask a worker process to run a lambda; result() re-raises."""
    print("submitting a lambda to a ProcessPoolExecutor")
    with ProcessPoolExecutor(1) as pool:
        future = pool.submit(lambda x: x * 2, 21)
        # error: _pickle.PicklingError: Can't pickle <function <lambda>>
        print(future.result())


if __name__ == "__main__":
    main()

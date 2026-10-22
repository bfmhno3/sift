"""functools.singledispatchmethod: one method, one body per type."""

from functools import singledispatchmethod

from sift.analysis import Pipeline, build_pipeline


class Analyze:
    """Turn a str, a list of str or a bytes object into terms."""

    def __init__(self, pipeline: Pipeline) -> None:
        """Keep the pipeline."""
        self.pipeline = pipeline

    @singledispatchmethod
    def terms(self, source: object) -> list[str]:
        """Reject a source type nobody registered."""
        raise TypeError(f"cannot analyze {type(source).__name__}")

    @terms.register
    def _(self, source: str) -> list[str]:
        """Analyze one string."""
        return self.pipeline.terms(source)

    @terms.register
    def _(self, source: list) -> list[str]:
        """Analyze each item and concatenate."""
        return [t for item in source for t in self.terms(item)]

    @terms.register
    def _(self, source: bytes) -> list[str]:
        """Decode as UTF-8, then analyze the string."""
        return self.terms(source.decode("utf-8"))


def main() -> None:
    """Dispatch on the type of the first argument after self."""
    analyze = Analyze(build_pipeline())
    print(analyze.terms("Kalman Filter"))
    print(analyze.terms(["Kalman", "卡尔曼滤波"]))
    print(analyze.terms("所有权".encode()))
    try:
        analyze.terms(3.5)
    except TypeError as exc:
        print("TypeError:", exc)


if __name__ == "__main__":
    main()

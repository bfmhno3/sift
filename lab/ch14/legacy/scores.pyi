from collections.abc import Mapping

def normalize(
    scores: Mapping[int, float], top: int | None = None
) -> list[tuple[int, float]]: ...

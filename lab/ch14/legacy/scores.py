"""A module written without annotations (the stub types it)."""


def normalize(scores, top=None):
    """Scale scores so the best one is 1.0; keep the best top."""
    best = max(scores.values(), default=0.0) or 1.0
    pairs = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(key, value / best) for key, value in pairs[:top]]

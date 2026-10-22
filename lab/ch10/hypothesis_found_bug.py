"""Hypothesis finds a bug in merge_sorted and shrinks the input.

``merge_sorted`` merges two sorted lists. The buggy version treats
equal heads as one element, so a duplicate disappears. The property
says the merge must equal ``sorted(a + b)``. Hypothesis tries random
lists until it fails, then shrinks the failing input to the smallest
one it can find. The script catches the failure, prints the falsifying
example and exits 0.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

SORTED_LISTS = st.lists(st.integers(), max_size=8).map(sorted)


def merge_sorted(a: list[int], b: list[int]) -> list[int]:
    """Return the merge of two sorted lists (buggy)."""
    out: list[int] = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            out.append(a[i])
            i += 1
        elif a[i] > b[j]:
            out.append(b[j])
            j += 1
        else:
            # BAD: equal heads are emitted once, so [0] + [0] -> [0]
            out.append(a[i])
            i += 1
            j += 1
    return out + a[i:] + b[j:]


def merge_sorted_fixed(a: list[int], b: list[int]) -> list[int]:
    """Return the merge of two sorted lists, keeping duplicates."""
    out: list[int] = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            out.append(a[i])
            i += 1
        else:
            out.append(b[j])
            j += 1
    return out + a[i:] + b[j:]


def make_property(merge):
    """Return a hypothesis test that checks merge against sorted()."""
    calls = []

    @settings(database=None, derandomize=True, max_examples=200)
    @given(SORTED_LISTS, SORTED_LISTS)
    def check(a: list[int], b: list[int]) -> None:
        calls.append((a, b))
        assert merge(a, b) == sorted(a + b)

    return check, calls


def main() -> None:
    """Run the property on the buggy and the fixed merge."""
    check, calls = make_property(merge_sorted)
    try:
        check()
    except AssertionError as error:
        print("buggy merge_sorted: property failed")
        # The report is attached to the exception as notes.
        notes = "\n".join(error.__notes__)
        print(notes.split("Explanation:")[0].rstrip())
        print(f"property calls, generating and shrinking: {len(calls)}")
        a, b = calls[-1]
        print(f"last call: merge_sorted({a}, {b}) = {merge_sorted(a, b)}")
    else:
        raise SystemExit("unexpected: the buggy merge passed")
    check, calls = make_property(merge_sorted_fixed)
    check()
    print(f"fixed merge_sorted: {len(calls)} examples, all passed")


if __name__ == "__main__":
    main()

"""`is` versus `==`: the small int cache and string interning."""

import sys


def runtime(text: str) -> int:
    """Build an int at run time, so the compiler cannot share it."""
    return int(text)


def main() -> None:
    """Probe the small int cache and the string intern table."""
    print("-- ints: -5 to 256 are preallocated singletons")
    for text in ("-6", "-5", "0", "256", "257", "1000"):
        a, b = runtime(text), runtime(text)
        print(f"  {text:>5}  ==: {a == b}  is: {a is b}")
    print("-- the same number twice in one code object may be shared")
    x = 1000
    y = 1000
    print("  x is y (constants of one code object):", x is y)
    print("-- strings: identifier-like literals are interned")
    s1 = "sift"
    s2 = "".join(["si", "ft"])
    print("  literal vs built at run time: ==", s1 == s2, " is", s1 is s2)
    s3 = sys.intern(s2)
    print("  after sys.intern(s2)        :", "is", s1 is s3)
    print("-- text that is not identifier-like")
    t1 = "hello world!"
    t2 = "".join(["hello ", "world!"])
    print("  ==", t1 == t2, " is", t1 is t2)
    print(
        "  sys.intern(t2) is sys.intern(t1):", sys.intern(t2) is sys.intern(t1)
    )
    print("-- single characters and the empty string are singletons")
    print("  chr(97) is chr(97):", chr(97) is chr(97))
    print("  ''.join([]) is ''.join([]):", "".join([]) is "".join([]))
    print("-- the rule for code: use == for values, is for None")
    print("  1000 is 1000 as a runtime fact proves nothing about equality")


if __name__ == "__main__":
    main()

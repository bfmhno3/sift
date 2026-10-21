"""List, dict and set comprehensions, nesting, conditions, scope."""


def main() -> None:
    """Print one example of each form."""
    words = ["Tea", "bike", "rust", "Kalman", "pid", "tea"]
    print([w.lower() for w in words])
    print([w for w in words if len(w) > 3])
    print([w.upper() if w.islower() else w for w in words])
    print({w.lower(): len(w) for w in words})
    print({w.lower() for w in words})
    matrix = [[1, 2, 3], [4, 5, 6]]
    print([x for row in matrix for x in row])
    print([[row[i] for row in matrix] for i in range(3)])
    print([(x, y) for x in range(3) for y in range(3) if x < y])
    squares = (n * n for n in range(5))
    print("generator expression:", sum(squares))
    # 推导式有自己的作用域，循环变量不会泄漏到外面
    n = "outer"
    _ = [n for n in range(3)]
    print("n after comprehension:", n)
    print("walrus:", [y for x in range(6) if (y := x * x) > 5])


if __name__ == "__main__":
    main()

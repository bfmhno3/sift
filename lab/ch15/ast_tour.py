"""ast: parse, dump, rewrite x ** 2 into x * x, compile, exec."""

import ast

SOURCE = """\
def area(x):
    return x ** 2 + 1
"""


class Square(ast.NodeTransformer):
    """Rewrite ``name ** 2`` into ``name * name``."""

    def __init__(self) -> None:
        self.count = 0

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)  # children first
        if (
            isinstance(node.op, ast.Pow)
            and isinstance(node.left, ast.Name)
            and isinstance(node.right, ast.Constant)
            and node.right.value == 2
        ):
            self.count += 1
            return ast.copy_location(
                ast.BinOp(node.left, ast.Mult(), node.left), node
            )
        return node


def main() -> None:
    """Parse, transform, unparse, compile and run."""
    tree = ast.parse(SOURCE)
    print("-- ast.dump(indent=2)")
    print(ast.dump(tree, indent=2))
    print("-- the same, as a one-liner expression")
    print(ast.dump(ast.parse("x ** 2", mode="eval").body))
    transformer = Square()
    new_tree = ast.fix_missing_locations(transformer.visit(tree))
    print("-- rewrites:", transformer.count)
    print(ast.unparse(new_tree))
    print("-- compile + exec")
    namespace: dict[str, object] = {}
    code = compile(new_tree, "<rewritten>", "exec")
    exec(code, namespace)
    area = namespace["area"]
    print("  area(7) =", area(7))  # type: ignore[operator]
    original: dict[str, object] = {}
    exec(compile(SOURCE, "<original>", "exec"), original)
    print("  same answer:", area(7) == original["area"](7))  # type: ignore[operator]
    print("-- literal_eval on a safe literal")
    print(" ", ast.literal_eval("{'a': [1, 2, (3, 4)]}"))
    print("-- walk: names used")
    print(
        " ", sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)})
    )


if __name__ == "__main__":
    main()

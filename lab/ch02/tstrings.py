"""Python 3.14 template strings (PEP 750)."""

import html
from string.templatelib import Interpolation, Template, convert


def render_html(template: Template) -> str:
    """Render a template, escaping every interpolated value."""
    parts: list[str] = []
    for item in template:
        if isinstance(item, Interpolation):
            value = convert(item.value, item.conversion)
            parts.append(html.escape(format(value, item.format_spec)))
        else:
            parts.append(item)
    return "".join(parts)


def main() -> None:
    """Show what a Template holds and why it is safer than an f-string."""
    name = "<b>Tom & Jerry</b>"
    count = 3.14159
    t = t"hello {name!r:>5} and {count:.2f}"
    print(type(t).__name__, t.strings)
    for item in t.interpolations:
        print(" ", item.expression, item.conversion, repr(item.format_spec))
    print(repr(t.values))
    print(f"<p>{name}</p>")
    print(render_html(t"<p>{name}</p>"))
    print(render_html(t"<td>{count:.2f}</td><td>{name!s}</td>"))
    print(isinstance(t, str), isinstance(t, Template))
    print(Template("a", Interpolation(1, "x"), "b").values)


if __name__ == "__main__":
    main()

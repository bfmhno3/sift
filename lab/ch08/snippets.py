"""Snippets, plain and HTML, and t-string escaping of <script>."""

from sift.snippet import html, make_snippet, render_html, render_plain

TEXT = (
    "An unrelated opening sentence about tea. " * 3
    + "Use <script>alert('x')</script> & friends with the Kalman "
    + "filter: predict, then update the Kalman state. "
    + "An unrelated closing sentence about rivers. " * 4
)


def main() -> None:
    """Cut a window around the hits and render it both ways."""
    parts = make_snippet(TEXT, {"kalman", "filter"}, width=120)
    print("parts:")
    for text, hit in parts:
        print(f"  {hit!s:<5} {text!r}")
    print("plain:", render_plain(parts))
    print("html: ", render_html(parts))
    danger = "<script>alert(1)</script>"
    template = t"<p>{danger}</p>"
    print("template strings:", template.strings)
    print("template values: ", template.values)
    print("html(t-string):  ", html(template))
    print("f-string:        ", f"<p>{danger}</p>")
    print("conversion:      ", html(t"<b>{danger!r}</b>"))
    print("no hits:", render_plain(make_snippet(TEXT, {"zzz"}, width=40)))


if __name__ == "__main__":
    main()

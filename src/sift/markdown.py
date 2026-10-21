"""Markdown helpers: front matter splitting and plain-text stripping."""

import re

_FENCE = re.compile(r"^\s*(```|~~~).*$")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>|<!--.*?-->")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_QUOTE = re.compile(r"^\s*>+\s?")
_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_ITALIC_STAR = re.compile(r"\*(?=\S)([^*]+?)(?<=\S)\*")
_ITALIC_UNDER = re.compile(r"(?<!\w)_(?=\S)([^_]+?)(?<=\S)_(?!\w)")
_STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_CODE_SPAN = re.compile(r"`+([^`]*)`+")


def split_front_matter(text: str) -> tuple[str, str]:
    """Split text into front matter and body.

    The front matter is returned without its two ``---`` lines. A text
    that does not start with a front matter block yields ``("", text)``.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return "".join(lines[1:i]), "".join(lines[i + 1 :])
    return "", text


def _strip_inline(line: str) -> str:
    """Remove inline Markdown syntax from one line of prose."""
    line = _IMAGE.sub("", line)
    line = _LINK.sub(r"\1", line)
    line = _AUTOLINK.sub(r"\1", line)
    line = _HTML_TAG.sub("", line)
    line = _CODE_SPAN.sub(r"\1", line)
    line = _BOLD.sub(r"\2", line)
    line = _STRIKE.sub(r"\1", line)
    line = _ITALIC_STAR.sub(r"\1", line)
    return _ITALIC_UNDER.sub(r"\1", line)


def strip_markdown(body: str) -> str:
    """Return the plain text of a Markdown body.

    Fence markers are dropped but the code inside is kept. Link text is
    kept while URLs, images, HTML tags, table pipes, heading markers and
    emphasis markers are removed.
    """
    out: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            out.append(line)
            continue
        if _TABLE_RULE.match(line) and "-" in line:
            continue
        line = _HEADING.sub("", line)
        line = _QUOTE.sub("", line)
        if line.lstrip().startswith("|"):
            line = line.replace("|", " ")
        line = _strip_inline(line)
        if "|" in line and line.count("|") >= 2:
            line = line.replace("|", " ")
        out.append(line.strip())
    return "\n".join(out)

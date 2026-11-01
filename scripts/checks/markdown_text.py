"""Markdown reading for the message checks: lines outside code, headings, sentences.

The checks read the source text a message is written in. A line inside a fenced code block
or an HTML comment is code, not prose; the helpers mark it so the checks can skip it.
"""
import re

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```+|~~~+)")
LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|(\d+)[.)])\s+(.*)$")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
LINK_TARGET = re.compile(r"\]\(([^)\s]*)\)")
QUOTED = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”")
SENTENCE_END = re.compile(r"[.?!][\"”’')\]*_]*(?=\s|$)")


class Line:
    """One source line: its number from 1, its text, and whether it is code."""

    def __init__(self, number, text, code, fence=None):
        self.number = number
        self.text = text
        self.code = code
        self.fence = fence


def read_lines(text):
    """Every line, with fenced code blocks and HTML comments marked as code.

    A fenced line carries the opening fence's info string (for example `text`) in `fence`.
    """
    result = []
    fence = None
    info = None
    comment = False
    for number, raw in enumerate(text.splitlines(), 1):
        if fence is not None:
            closing = FENCE.match(raw)
            if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= len(fence) \
                    and not raw.strip()[len(closing.group(1)):].strip():
                result.append(Line(number, raw, True, info))
                fence = None
                continue
            result.append(Line(number, raw, True, info))
            continue
        opening = FENCE.match(raw)
        if opening and not comment:
            fence = opening.group(1)
            info = raw.strip()[len(fence):].strip()
            result.append(Line(number, raw, True, info))
            continue
        stripped = raw.strip()
        if comment:
            result.append(Line(number, raw, True))
            if "-->" in stripped:
                comment = False
            continue
        if stripped.startswith("<!--"):
            result.append(Line(number, raw, True))
            comment = "-->" not in stripped
            continue
        result.append(Line(number, raw, False))
    return result


def heading(line):
    """(level, text) for a heading line, else None."""
    if line.code:
        return None
    match = HEADING.match(line.text)
    if not match:
        return None
    return len(match.group(1)), match.group(2)


def mask(text):
    """The text with code spans, link targets and quotations blanked, keeping every offset.

    Sentence splitting and pattern matching on the masked text ignore punctuation and words
    inside them; offsets still point into the original text.
    """
    chars = list(text)
    for pattern in (CODE_SPAN, LINK_TARGET, QUOTED):
        for match in pattern.finditer("".join(chars)):
            start, end = match.span()
            for index in range(start + 1, end - 1):
                chars[index] = "x"
    return "".join(chars)


def sentences(text):
    """The sentences of one paragraph, split as rules/writing.md counts them."""
    masked = mask(text)
    result = []
    start = 0
    for match in SENTENCE_END.finditer(masked):
        piece = text[start:match.end()].strip()
        if piece:
            result.append(piece)
        start = match.end()
    tail = text[start:].strip()
    if tail:
        result.append(tail)
    return result

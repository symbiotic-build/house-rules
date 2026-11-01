"""Markdown reading shared by the message checks: lines outside code, headings, blocks, sentences.

The checks read the source text a message is written in. A line inside a fenced code block
or an HTML comment is code, not prose; the helpers mark it so the checks can skip it.
"""
import re

LABELS = ("FACT", "ASSUMPTION", "ESTIMATE", "ASSESSMENT", "DECISION")
LABEL = re.compile(r"`(" + "|".join(LABELS) + r")`")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```+|~~~+)")
LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|(\d+)[.)])\s+(.*)$")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
LINK_TARGET = re.compile(r"\]\(([^)\s]*)\)")
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
QUOTED = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”")
BOLD_START = re.compile(r"^\*\*[^*]+\*\*")
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


def bold_start(text):
    """The bold span a line opens with (`**…**`), found outside code spans, or ""."""
    match = BOLD_START.match(mask(text))
    return text[:match.end()] if match else ""


def first_label(sentence):
    """The first claim label in a sentence, or None."""
    match = LABEL.search(sentence)
    return match.group(1) if match else None


def blocks(lines):
    """Prose blocks outside code: headings, list items with their continuation lines, paragraphs.

    Each block is (first line number, joined text, kind), where kind is `heading`, `item` or
    `paragraph`. A blank line, a heading, a code line or a new list item ends a block.
    """
    result = []
    current = None

    def close():
        nonlocal current
        if current is not None:
            result.append((current[0], " ".join(current[1]), current[2]))
            current = None

    for line in lines:
        if line.code or not line.text.strip():
            close()
            continue
        if heading(line):
            close()
            result.append((line.number, heading(line)[1], "heading"))
            continue
        item = LIST_ITEM.match(line.text)
        if item:
            close()
            current = (line.number, [item.group(3).strip()], "item")
            continue
        if current is None:
            current = (line.number, [line.text.strip()], "paragraph")
        else:
            current[1].append(line.text.strip())
    close()
    return result


def first_prose_line(lines):
    """The first line that is neither blank nor code, or None."""
    for line in lines:
        if not line.code and line.text.strip():
            return line
    return None

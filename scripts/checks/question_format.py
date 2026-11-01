#!/usr/bin/env python3
"""Check an operator message against rules/session-writing.md §Questions to the operator.

Usage: question_format.py [message.md]   (standard input when absent or -)

Prints one JSON line per finding and exits 0 when the questions follow the format, 2 when
they do not and 1 when the input cannot be read. A message without questions passes.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import findings  # noqa: E402
import markdown_text as md  # noqa: E402

CHECK = "question_format"
NUMBERED = re.compile(r"^(\d+)([a-z])?(\\?)\.\s*(.*)$")
OPTION = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
BULLET = re.compile(r"^(\s+)[-*+]\s+")
BOLD_LINE = re.compile(r"^\*\*(.+)\*\*$")
RECOMMENDED = re.compile(r"\(recommended\)[.:]?$")
ANSWER = "**Answer like so:**"
CONTEXT_FLAGS = ("FACT", "ASSESSMENT")
# Work the agent's own team does: the rule lists tests, replays and verification as examples.
TEAM_WORK = re.compile(
    r"\b(verify|verification|replay|reproduce|re-?run|re-?test|benchmark)\b|"
    r"\b(run|start|do|perform|execute|repeat|redo|write|add)\b.{0,40}\b(tests?|testing|replays?|verification|"
    r"benchmarks?|reproductions?|spot[- ]checks?)\b|"
    # "test" as a verb ("Should I test the upload?"), not as a modifier ("the test account").
    r"\b(i|we|you|to|please) (re-?)?test\b|\btest (it|this|that|them|these|those|the|a|an)\b", re.IGNORECASE)
CONTEXT_REQUEST = re.compile(r"\b(explain|why|how|what|which|more|context|detail\w*|clarify|example|evidence|"
                             r"cost|show|tell|describe|compare)\b", re.IGNORECASE)
REPLY_LINE = re.compile(r"^(reply|answer|your answer|response|choice)\s*:|_{3,}|\[ \]", re.IGNORECASE)


class Question:
    def __init__(self, line, level, number, suffix, escaped, title):
        self.line = line
        self.level = level
        self.number = number
        self.suffix = suffix
        self.escaped = escaped
        self.title = title
        self.topic = None
        self.body = []


def question_heading(level, text):
    """(number or None, letter suffix, escaped, title) when a heading asks a question, else None.

    A heading asks a question when it ends with a question mark, or when it is a numbered
    level-3 heading. A numbered topic heading at level 2 is not a question.
    """
    match = NUMBERED.match(text)
    asks = text.rstrip().endswith("?")
    if match and (asks or level == 3):
        return int(match.group(1)), match.group(2), bool(match.group(3)), match.group(4)
    if asks:
        return None, None, False, text
    return None


def check(text):
    lines = md.read_lines(text)
    found = []
    questions = []
    topic = None
    current = None
    answer_index = None
    loose = []  # option lines that sit outside any question section
    asked_in_prose = []  # prose lines outside any question section that ask a question
    for index, line in enumerate(lines):
        if not line.code and line.text.strip() == ANSWER:
            answer_index = index
            current = None
            continue
        parsed = md.heading(line)
        if parsed:
            level, title = parsed
            if level <= 2:
                topic = title if level == 2 else None
            asked = question_heading(level, title)
            if asked:
                number, suffix, escaped, rest = asked
                current = Question(line.number, level, number, suffix, escaped, rest)
                current.topic = topic
                questions.append(current)
            else:
                current = None
            continue
        if current is not None:
            current.body.append(line)
        elif not line.code and OPTION.match(line.text) and "(recommended)" in line.text:
            loose.append(line)
        elif not line.code and any(md.mask(sentence).rstrip("*_ ").endswith("?")
                                   for _, sentence in md.sentences(line.text.strip())):
            asked_in_prose.append(line)

    for line in loose:
        found.append(findings.finding(
            CHECK, "options_without_question", "a recommended option list sits outside a numbered level-3 "
            "question heading; write the question as `### N\\. …?` above its options", line.number))

    for line in asked_in_prose:
        found.append(findings.finding(
            CHECK, "question_outside_heading", "the text asks the operator a question outside a question heading; "
            "write it as `### N\\. …?` under a level-2 topic, or state it without a question", line.number))

    expected = 1
    seen = {}
    for question in questions:
        found.extend(check_heading(question, expected, seen))
        if question.number is not None:
            expected = question.number + 1
        found.extend(check_body(question))

    if questions:
        found.extend(check_answer_block(lines, answer_index))
        if answer_index is not None and questions[-1].line > lines[answer_index].number:
            found.append(findings.finding(CHECK, "answer_block_order", "a question follows the answer prompt; put "
                                          "\"Answer like so:\" after the complete question list",
                                          lines[answer_index].number))
    elif answer_index is not None:
        found.append(findings.finding(CHECK, "answer_block_without_questions",
                                      "the answer prompt appears without a fully written question list",
                                      lines[answer_index].number))
    return found


def check_heading(question, expected, seen):
    result = []
    line = question.line
    if question.level != 3:
        result.append(findings.finding(CHECK, "question_level",
                                       f"a question heading is level {question.level}; write it as level 3 (###)", line))
    if question.topic is None:
        result.append(findings.finding(CHECK, "question_topic",
                                       "the question has no level-2 topic heading above it", line))
    if question.number is None:
        result.append(findings.finding(CHECK, "question_number_missing",
                                       "the question heading has no number; start it with `N\\.`", line))
        return result
    if question.suffix:
        result.append(findings.finding(CHECK, "question_number_suffix",
                                       f"question {question.number}{question.suffix} uses a letter; number "
                                       "questions 1, 2, 3 across the message", line))
    if not question.escaped:
        result.append(findings.finding(CHECK, "question_number_unescaped",
                                       f"write the number escaped, as `### {question.number}\\.`", line))
    if question.number in seen and not question.suffix:
        result.append(findings.finding(CHECK, "question_number_duplicate",
                                       f"question number {question.number} is also used on line "
                                       f"{seen[question.number]}", line))
    elif question.number != expected and not question.suffix:
        result.append(findings.finding(CHECK, "question_number_order",
                                       f"question number {question.number} follows {expected - 1}; number "
                                       f"questions 1, 2, 3 across topics", line))
    seen.setdefault(question.number, line)
    if TEAM_WORK.search(question.title):
        result.append(findings.finding(CHECK, "team_work",
                                       "the question asks about work the agent's own team does (tests, replays, "
                                       "verification); list it as an internal task instead", line))
    return result


def check_body(question):
    result = []
    prose = [line for line in question.body if not line.code]
    for line in question.body:
        stripped = line.text.strip()
        if line.code:
            continue
        if stripped.startswith(">") or (stripped.startswith("|") and stripped.endswith("|")):
            result.append(findings.finding(CHECK, "question_extra",
                                           "a question holds a quote or a table; give the context in sentences",
                                           line.number))
        elif REPLY_LINE.search(stripped):
            result.append(findings.finding(CHECK, "question_extra",
                                           "a question holds a reply line or an answer box; the answer example "
                                           "at the end shows how to answer", line.number))
        bullet = md.LIST_ITEM.match(line.text)
        if bullet and bullet.group(2) is None and ("(recommended)" in bullet.group(3)
                                                   or BOLD_LINE.match(bullet.group(3).strip())):
            result.append(findings.finding(CHECK, "options_not_numbered",
                                           "a choice is written as a bullet; write the options as a numbered list "
                                           "so the operator can answer with a number", line.number))
    # The context: the first paragraph under the heading, before any list.
    context = []
    for line in prose:
        if not line.text.strip():
            if context:
                break
            continue
        if md.LIST_ITEM.match(line.text):
            break
        context.append(line)
    if not context:
        result.append(findings.finding(CHECK, "context_missing",
                                       "the question has no context line below its heading", question.line))
    else:
        result.extend(check_context(context))
    result.extend(check_options(prose, question))
    return result


def check_context(context):
    result = []
    first = context[0]
    if len(context) > 1:
        if not (first.text.rstrip().endswith("\\") and len(context) == 2):
            result.append(findings.finding(CHECK, "context_wrapped",
                                           "write all context sentences on one source line; only a line ending in "
                                           "a backslash may be followed by the line on what happens next",
                                           context[1].number))
    text = first.text.strip().rstrip("\\").rstrip()
    for _, sentence in md.sentences(text):
        flag = re.match(r"`(\w+)`", sentence)
        if not flag or flag.group(1) not in CONTEXT_FLAGS:
            got = f"starts with `{flag.group(1)}`" if flag else "has no flag"
            result.append(findings.finding(CHECK, "context_flag",
                                           f"a context sentence {got}; start it with `FACT` or `ASSESSMENT`: "
                                           f"{sentence[:80]}", first.number))
    return result


def check_options(prose, question):
    result = []
    options = []
    for line in prose:
        match = OPTION.match(line.text)
        if match:
            if match.group(1):
                result.append(findings.finding(CHECK, "options_nested",
                                               "an option list is nested; write the options as one flat numbered list",
                                               line.number))
                continue
            options.append((line, int(match.group(2)), match.group(3).strip()))
        elif options and BULLET.match(line.text):
            result.append(findings.finding(CHECK, "options_nested",
                                           "an option has a nested list; give its change and side effect in its line",
                                           line.number))
    if not options:
        return result
    for position, (line, number, _) in enumerate(options, 1):
        if number != position:
            result.append(findings.finding(CHECK, "options_numbering",
                                           f"option {number} should be {position}; number options 1, 2, 3",
                                           line.number))
            break
    recommended = []
    for line, number, body in options:
        if re.search(r"\boption\b", body, re.IGNORECASE):
            result.append(findings.finding(CHECK, "option_word",
                                           "do not write the word \"Option\" in option text", line.number))
        bold = BOLD_LINE.match(body)
        marked = "(recommended)" in body
        if bold and RECOMMENDED.search(bold.group(1).strip()):
            recommended.append(line)
        elif marked or bold:
            result.append(findings.finding(CHECK, "recommended_format",
                                           "write the whole recommended line in bold and end it with "
                                           "\"(recommended)\": `1. **… (recommended).**`", line.number))
            if marked:
                recommended.append(line)
    if len(recommended) != 1:
        result.append(findings.finding(CHECK, "recommended_count",
                                       f"the question recommends {len(recommended)} options; recommend exactly one",
                                       question.line))
    return result


def check_answer_block(lines, answer_index):
    if answer_index is None:
        return [findings.finding(CHECK, "answer_block_missing",
                                 "end the question list with the bold line \"Answer like so:\" and a "
                                 "three-line `text` example", None)]
    result = []
    rest = lines[answer_index + 1:]
    opening = next((line for line in rest if line.text.strip()), None)
    if opening is None or not opening.code or opening.fence != "text" or not md.FENCE.match(opening.text):
        return [findings.finding(CHECK, "answer_block_format",
                                 "follow \"Answer like so:\" with a `text` code block",
                                 lines[answer_index].number)]
    start = rest.index(opening) + 1
    body = []
    for line in rest[start:]:
        if md.FENCE.match(line.text):
            break
        body.append(line)
    if len(body) != 3 or any(not re.match(r"^ \S", line.text) for line in body):
        result.append(findings.finding(CHECK, "answer_block_format",
                                       "the answer example has three lines, each indented by one space",
                                       opening.number))
        return result
    answers = [re.sub(r"^\d+\\?\.\s*", "", line.text.strip()) for line in body]
    numbered = all(re.match(r"^\d+\\?\.\s+\S", line.text.strip()) for line in body)
    choice = any(re.fullmatch(r"\d+", answer) for answer in answers)
    agreed = any(answer.lower() == "ok" for answer in answers)
    text = any(CONTEXT_REQUEST.search(answer) for answer in answers)
    if not (numbered and choice and agreed and text):
        result.append(findings.finding(CHECK, "answer_block_format",
                                       "the answer example shows, by question number, an option number, a request "
                                       "for more context and `ok`", opening.number))
    return result


def main(argv=None):
    args = findings.parser(__doc__.splitlines()[0]).parse_args(argv)
    return findings.finish(check(findings.read_text(args.path)))


if __name__ == "__main__":
    sys.exit(main())

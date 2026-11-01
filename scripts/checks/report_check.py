#!/usr/bin/env python3
"""Check an operator report against rules/writing.md §Claim labels and §Checks before sending.

Usage: report_check.py [--plan campaign.json] [message.md]   (standard input when absent or -)

Checks that:
- every `FACT` sentence carries a source: a link, a path, an inline-code command or a quote;
- every claim taken from another agent's report is labelled `ASSUMPTION`, which names that source;
- every field the plan's `required_report_field` constraints name appears as a heading or a bold label;
- no sentence sends the reader to text elsewhere ("see above", "my last message");
- when the report names an operator-only blocker, the first line is bold and names each one.

Prints one JSON line per finding and exits 0 on pass, 2 on fail and 1 when an input cannot
be read.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blocker_classify  # noqa: E402
import findings  # noqa: E402
import markdown_text as md  # noqa: E402

CHECK = "report_check"
LINK = re.compile(r"\[[^\]]+\]\([^)\s]+\)|https?://\S+")
CODE = re.compile(r"`([^`]+)`")
QUOTE = re.compile(r"\"[^\"]{2,}\"|“[^”]{2,}”")
PATH = re.compile(r"(?:~|\.{1,2})?/?[\w.-]+/[\w.-]+/[\w./-]*|(?<![\w/])[\w.-]+/[\w-]+\.\w+|"
                  r"\b[\w-]+\.(?:py|md|json|jsonl|rs|ts|js|toml|ya?ml|sh|log|txt|tsv|csv)\b(?::\d+)?")
AGENT = r"(?:lane|worker|subagent|sub-agent|agent|reviewer|session)"
RELAY = re.compile(
    AGENT + r"(?:'s|s'|s)?\s+(?:own\s+)?(?:report|reports|reported|found|finds|findings?|measured|measurements?|"
    r"estimates?|estimated|research|plan|says|said|claims?|claimed|states|stated|notes?|summary|results?|counts?)\b"
    r"|\baccording to (?:the |a |an )?(?:[\w-]+ )?" + AGENT +
    r"|\b(?:reported|found|measured|estimated) by (?:the |a |an )?(?:[\w-]+ )?" + AGENT,
    re.IGNORECASE)
ELSEWHERE = [
    re.compile(r"\bsee (?:above|earlier|previous|the (?:pr|pull request|issue|thread|report|brief|doc|document|"
               r"message|plan|link))\b", re.IGNORECASE),
    re.compile(r"\b(?:as )?(?:discussed|mentioned|noted|described|explained|stated|listed) (?:above|earlier|before|"
               r"previously)\b", re.IGNORECASE),
    re.compile(r"\b(?:my|the|your) (?:last|previous|earlier|prior) (?:message|reply|report|update|note|answer)\b",
               re.IGNORECASE),
    re.compile(r"\b(?:questions?|points?|items?|list|table|options?|section) above\b", re.IGNORECASE),
    re.compile(r"\bthe (?:report|brief|document|doc|plan|pr|message) (?:also )?(?:asks|says|lists|covers|explains|"
               r"holds|contains)\b", re.IGNORECASE),
    re.compile(r"\bas (?:discussed|agreed) (?:earlier|before)?", re.IGNORECASE),
]
BOLD_START = re.compile(r"^\*\*[^*]+\*\*")


def has_source(claim):
    """True when a claim names its evidence: a link, a path, a code span other than a label, or a quote."""
    if LINK.search(claim) or QUOTE.search(claim):
        return True
    if any(match.group(1) not in md.LABELS for match in CODE.finditer(claim)):
        return True
    return bool(PATH.search(CODE.sub(" ", claim)))


def check_claims(lines):
    result = []
    for number, text, _ in md.blocks(lines):
        label = None
        for offset, sentence in md.sentences(text):
            own = md.first_label(sentence)
            if own:
                label = own
            masked = md.mask(sentence)
            if label == "FACT":
                # A label can cover a paragraph; every sentence it covers still names its evidence.
                claim = sentence[sentence.index("`FACT`") + len("`FACT`"):] if own == "FACT" else sentence
                if not has_source(claim):
                    result.append(findings.finding(
                        CHECK, "fact_source", "a `FACT` sentence names no source; add the path, command, link "
                        f"or quoted output it was checked against: {sentence[:100]}", number))
            if RELAY.search(masked) and label != "ASSUMPTION":
                got = f"labelled `{label}`" if label else "unlabelled"
                result.append(findings.finding(
                    CHECK, "relay_label", f"a claim from another agent's report is {got}; label it `ASSUMPTION` "
                    f"and name its source, or verify it first: {sentence[:100]}", number))
            for pattern in ELSEWHERE:
                match = pattern.search(masked)
                if match:
                    result.append(findings.finding(
                        CHECK, "reference_elsewhere", f"\"{sentence[match.start():match.end()]}\" sends the reader "
                        "to text elsewhere; restate what it refers to", number))
                    break
    return result


def normalize(text):
    text = re.sub(r"[*_`]", "", text)
    text = re.sub(r"^\d+\\?\.\s*", "", text.strip())
    return re.sub(r"\s+", " ", text).strip().rstrip(":").strip().lower()


def labels(lines):
    """The headings and bold labels of a report, normalized for comparison with field names."""
    result = set()
    for line in lines:
        if line.code:
            continue
        parsed = md.heading(line)
        if parsed:
            result.add(normalize(parsed[1]))
            continue
        item = md.LIST_ITEM.match(line.text)
        body = item.group(3) if item else line.text.strip()
        bold = BOLD_START.match(body)
        if bold:
            result.add(normalize(bold.group(0)))
        if body.startswith("|"):
            cells = [cell for cell in body.strip("|").split("|")]
            if cells:
                result.add(normalize(cells[0]))
    return result


def required_fields(plan_path):
    """The `field` of every `required_report_field` constraint in a campaign plan file."""
    text = findings.read_text(plan_path)
    try:
        plan = json.loads(text)
    except ValueError as error:
        print(f"{plan_path} is not JSON: {error}", file=sys.stderr)
        raise SystemExit(findings.INPUT_ERROR)
    constraints = plan.get("constraints", []) if isinstance(plan, dict) else None
    if not isinstance(constraints, list):
        print(f"{plan_path}: `constraints` must be a list", file=sys.stderr)
        raise SystemExit(findings.INPUT_ERROR)
    result = []
    for constraint in constraints:
        rule = constraint.get("rule") if isinstance(constraint, dict) else None
        if isinstance(rule, dict) and rule.get("kind") == "required_report_field" and isinstance(rule.get("field"), str):
            result.append(rule["field"])
    return result


def check_fields(lines, fields):
    present = labels(lines)
    return [findings.finding(CHECK, "required_field", f"the plan requires the field \"{field}\"; give it as a "
                             "heading or a bold label", None, field=field)
            for field in fields if normalize(field) not in present]


def check_blocker_line(lines):
    first = md.first_prose_line(lines)
    parsed = md.heading(first) if first else None
    if parsed and parsed[0] == 1:
        # A report file opens with its title; the line after it is the first line.
        first = md.first_prose_line(lines[lines.index(first) + 1:])
    if first is None:
        return []
    bold = BOLD_START.match(first.text.strip())
    bold_text = bold.group(0) if bold else ""
    # The unbold rest of the first line counts with the body: the bold span must name each blocker.
    rest = "\n".join([first.text.strip()[len(bold_text):]] +
                     [line.text for line in lines if not line.code and line is not first])
    named = {}
    for name, matched, _ in blocker_classify.operator_only_mentions(rest):
        named.setdefault(name, matched)
    first_named = {name for name, _, _ in blocker_classify.operator_only_mentions(bold_text)}
    result = []
    if named and not first_named:
        result.append(findings.finding(
            CHECK, "blocker_first", "the report names an operator-only blocker ("
            + ", ".join(sorted(named)) + "); open it with a bold line that names it", first.number))
    missing = sorted(set(named) - first_named)
    if missing and first_named:
        result.append(findings.finding(
            CHECK, "blocker_first", "the bold first line does not name every operator-only blocker the report "
            "names; missing: " + ", ".join(f"{name} (\"{named[name]}\")" for name in missing), first.number))
    for line in lines:
        if line is first or line.code:
            continue
        item = md.LIST_ITEM.match(line.text)
        body = item.group(3) if item else line.text.strip()
        if re.match(r"^\*\*(operator-only )?blockers?\b", body, re.IGNORECASE):
            result.append(findings.finding(CHECK, "blocker_first", "a blocker line appears after the first line; "
                                           "move it to the first line", line.number))
    return result


def check(text, fields=()):
    lines = md.read_lines(text)
    return check_blocker_line(lines) + check_claims(lines) + check_fields(lines, fields)


def main(argv=None):
    parser = findings.parser(__doc__.splitlines()[0])
    parser.add_argument("--plan", help="campaign plan file (JSON) whose required_report_field constraints apply")
    args = parser.parse_args(argv)
    fields = required_fields(args.plan) if args.plan else []
    return findings.finish(check(findings.read_text(args.path), fields))


if __name__ == "__main__":
    sys.exit(main())

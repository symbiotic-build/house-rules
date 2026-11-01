"""Input and output shared by the House Rules checks.

Every check reads one path, or standard input when the path is absent or `-`, and prints
one JSON object per finding on standard output. The exit status is 0 when the input
passes, 2 when it fails and 1 when the input cannot be read or the arguments are wrong.
"""
import argparse
import json
import sys
from pathlib import Path

PASS = 0
INPUT_ERROR = 1
FAIL = 2


class Parser(argparse.ArgumentParser):
    """An argument parser whose usage errors exit 1, so status 2 always means a failed check."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: {message}", file=sys.stderr)
        raise SystemExit(INPUT_ERROR)


def parser(description):
    """A parser that takes the optional input path every check reads."""
    result = Parser(description=description)
    result.add_argument("path", nargs="?", default="-", help="input file; standard input when absent or -")
    return result


def read_text(path):
    """The input text; exits 1 with the reason when the file cannot be read."""
    try:
        if path == "-":
            return sys.stdin.read()
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"cannot read {path}: {error}", file=sys.stderr)
        raise SystemExit(INPUT_ERROR)


def finding(check, rule, message, line=None, **detail):
    """One finding: the check, the rule it breaks, the input line when known, and the reason."""
    record = {"check": check, "rule": rule, "line": line, "message": message}
    record.update(detail)
    return record


def finish(records, failed=None):
    """Print each record as one JSON line and return the exit status.

    A check fails when it printed any record, unless the caller decides with `failed`.
    """
    for record in records:
        print(json.dumps(record, ensure_ascii=False))
    if failed is None:
        failed = bool(records)
    return FAIL if failed else PASS

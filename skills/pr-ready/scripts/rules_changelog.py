#!/usr/bin/env python3
"""Print the rules changelog, built from the merge commits on a branch.

A rule-changing pull request records why each rule changed in its `## Rule changes` section.
The merge copies that section into the merge commit message (pr-ready §4), so the history
lives in Git and no tracked changelog file is edited by hand. CHANGELOG-RULES.md is the
frozen archive of entries recorded before this; it stays approval evidence.

  rules_changelog.py [--repo PATH] [--rev REV]          print the changelog, newest first
  rules_changelog.py --section < PR-BODY                print the body's Rule changes section,
                                                        heading included, for the merge commit;
                                                        exit 1 when the body has none
  rules_changelog.py --check [--repo PATH] [--rev REV]  list first-parent merges that changed
                                                        rule text without a Rule changes
                                                        section; exit 1 when any exist

--check starts at the commit on REV's first-parent line that brought this script in (for a
merged pull request, its merge commit): merges before it predate the convention, including
merges that landed while the script's branch was still open.

Rule text is what the preparer's rule-change report covers at each merge's first parent:
its default rule paths plus that commit's .rule-changes.json extensions.
"""
import argparse
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import prepare  # noqa: E402


def section(body):
    """The Rule changes section's text without its heading, found by the preparer's own parser
    (outside fences and comments), or None."""
    lines = prepare.declared_rule_changes(body.replace("\r\n", "\n"))
    return "\n".join(line for _, line in lines[1:]).strip() if lines else None

# The first merge that carries its Rule changes section; older merges are in the archive.
ARCHIVE_NOTE = "Entries recorded before this changelog are in [CHANGELOG-RULES.md](CHANGELOG-RULES.md)."


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL).stdout


def merges(repo, rev):
    """First-parent merge commits in rev (a revision or range), newest first: (sha, date, subject, body)."""
    out = git(repo, "log", "--first-parent", "--merges", "--format=%H%x1f%cs%x1f%s%x1f%b%x1e", rev)
    for record in out.split("\x1e"):
        if record.strip():
            sha, date, subject, body = record.strip("\n").split("\x1f", 3)
            yield sha, date, subject, body


def changed_rules(repo, sha):
    """Paths under the rule-change report that the merge changed against its first parent."""
    _, patterns = prepare.rule_policy(repo, f"{sha}^1")
    paths = git(repo, "diff", "--name-only", "--no-renames", "-z", f"{sha}^1", sha).split("\0")
    return [p for p in paths if p and any(pattern.fullmatch(p) for pattern in patterns)]


def changelog(repo, rev):
    parts = ["# Rules changelog\n", "Generated from the merge commits on "
             f"`{rev}` by skills/pr-ready/scripts/rules_changelog.py. Do not edit.\n"]
    for sha, date, subject, body in merges(repo, rev):
        text = section(body)
        if text is not None:
            parts.append(f"\n## {date} — {subject} ({sha[:12]})\n\n{text}\n")
    parts.append(f"\n{ARCHIVE_NOTE}\n")
    return "".join(parts)


def missing(repo, rev):
    # First-parent history compares each commit with its first parent, so this finds the merge
    # (or direct commit) on rev's main line that brought the script in.
    added = git(repo, "log", "--first-parent", "--diff-filter=A", "--format=%H", rev, "--",
                "skills/pr-ready/scripts/rules_changelog.py").split()
    span = f"{added[-1]}^1..{rev}" if added else rev
    return [(sha, subject, paths) for sha, _, subject, body in merges(repo, span)
            if section(body) is None and (paths := changed_rules(repo, sha))]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default=str(pathlib.Path(__file__).resolve().parents[3]))
    parser.add_argument("--rev", default="HEAD")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--section", action="store_true")
    args = parser.parse_args(argv)
    if args.section:
        text = section(sys.stdin.read())
        if not text:
            print("the pull request body has no Rule changes section", file=sys.stderr)
            return 1
        print("## Rule changes\n\n" + text)
        return 0
    if not args.check:
        sys.stdout.write(changelog(args.repo, args.rev))
        return 0
    gaps = missing(args.repo, args.rev)
    for sha, subject, paths in gaps:
        print(f"{sha[:12]} {subject}: changed {', '.join(paths)} without a Rule changes section")
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())

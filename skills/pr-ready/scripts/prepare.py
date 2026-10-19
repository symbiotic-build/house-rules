#!/usr/bin/env python3
"""Prepare local review, fix and PR context; registered specifications use the shared checker."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import quote, quote_from_bytes, unquote, urlsplit

HERE = Path(__file__).resolve().parent


def checker_unavailable():
    """Name why the shared specification checker cannot run here, or return None."""
    if sys.version_info < (3, 11):
        return (f"this preparer runs Python {sys.version_info[0]}.{sys.version_info[1]} without REVIEW_PYTHON, "
                "and the shared checker needs 3.11 or later")
    if not (HERE.parents[1] / "spec-writing/scripts/spec_docs.py").is_file():
        return "the shared checker skills/spec-writing is not staged beside this preparer"
    import importlib.util
    if importlib.util.find_spec("markdown_it") is None:
        return "the shared checker's pinned dependencies are not installed for this Python"
    return None
CODEX_LIMIT = 800_000
SPEC_LIMIT = 2_000_000
COMMENT_LIMIT = 4_000
FULL_FILE_CAP = 85_000
LOCK = re.compile(r"(^|/)([^/]*\.lock|package-lock\.json|npm-shrinkwrap\.json|pnpm-lock\.yaml|go\.sum)$")
# Lenses that run no commands and review only the structured change part.
STRUCTURED_ONLY = ("generic",)
PACK_NOTICE = f"Size guard: prompt exceeds {CODEX_LIMIT:,} characters; change part uses pack (hunk headers)."
TEST = re.compile(r"(^|/)(tests?(/|\.)|test_[^/]*|[^/]*[_\-.](tests?|spec)\.[^/]+$)", re.I)


def redact(text):
    """Remove URL credentials at output boundaries; keep raw Git paths intact."""
    text = re.sub(r"(?<![a-z0-9+.-])([a-z][a-z0-9+.-]*://)[^/\s?#]*@", r"\1[REDACTED]@", text, flags=re.I)
    def query(match):
        key = unquote(match[2]).lower()
        if re.search(r"token|password|passwd|secret|credential|signature|key|^sig$|(?:^|[_-])(?:auth|authorization|oauth)(?:$|[_-])", key):
            return match[1] + match[2] + "=[REDACTED]"
        return match[0]
    # A key cannot consume another query start, so repeated '?' failures stay
    # linear. Parentheses belong to values, not their separators.
    return re.sub(r"([?&])([^?=&#\s]+)=([^&#\s\"'<>`]*)", query, text)


class PrepareError(Exception):
    def __init__(self, message):
        super().__init__(redact(message))



# Defaults are policy, extended by versioned base-commit configuration.
RULE_PATHS = ("INDEX.md", "STRUCTURE.md", "PREFERENCES.md", "INSTALL-AGENTS.md", "AGENTS.md",
              "CHANGELOG-RULES.md", "rules/**/*.md", "prompts/**/*.md", "skills/**/*.md",
              ".agents/rules.md", "CONTEXT.md")
RULE_PROVENANCE_PATHS = ("CHANGELOG-RULES.md",)
RULE_DEFAULTS = dict(version=1, extra_protected_paths=[], extra_provenance_paths=[], max_report_chars=80_000)


class RuleReportTooLarge(PrepareError):
    """A failed-closed report must reach the caller even though preparation fails."""

    def __init__(self, report):
        super().__init__("rule report FAILED CLOSED; narrow the range or repair the base configuration")
        self.report = report


def rule_glob(pattern):
    """Translate repository-relative globs, including zero-directory **/."""
    if (not isinstance(pattern, str) or not pattern or pattern.startswith("/")
            or any(part in ("", ".", "..") for part in pattern.split("/"))
            or "\0" in pattern or "\\" in pattern):
        raise PrepareError("invalid protected path pattern: " + repr(pattern))
    result, index = "", 0
    while index < len(pattern):
        if pattern[index:index + 3] == "**/":
            result += "(?:.*/)?"
            index += 3
        elif pattern[index:index + 2] == "**":
            result += ".*"
            index += 2
        else:
            char = pattern[index]
            result += "[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char)
            index += 1
    return re.compile(result + r"\Z", re.S)


def rule_blob(repo, revision, path, mode):
    if mode not in ("100644", "100755"):
        raise PrepareError(f"protected input is not a regular file: {revision}:{path}")
    text = git(repo, "show", f"{revision}:{path}")
    try:
        text.encode("utf-8")
    except UnicodeError as exc:
        raise PrepareError(f"protected input is not UTF-8: {revision}:{path}") from exc
    return text


def rule_policy(repo, base):
    policy = dict(RULE_DEFAULTS)
    path = ".rule-changes.json"
    entry = git(repo, "ls-tree", "-z", base, "--", path)
    if entry:
        try:
            configured = json.loads(rule_blob(repo, base, path, entry.split(" ", 1)[0]))
        except ValueError as exc:
            raise PrepareError(f"invalid {path}: {exc}") from exc
        if not isinstance(configured, dict) or set(configured) - set(policy):
            raise PrepareError(f"invalid {path}: expected known configuration fields")
        if type(configured.get("version")) is not int or configured["version"] != 1:
            raise PrepareError(f"invalid {path}: expected version 1")
        policy.update(configured)
    if (not isinstance(policy["extra_protected_paths"], list)
            or not isinstance(policy["extra_provenance_paths"], list)
            or type(policy["max_report_chars"]) is not int or policy["max_report_chars"] < 1):
        raise PrepareError("invalid .rule-changes.json: paths or limit")
    patterns = [rule_glob(pattern) for pattern in (*RULE_PATHS, *policy["extra_protected_paths"],
                                                 *policy["extra_provenance_paths"])]
    return policy, patterns


def closing_fence(row, fence):
    """Only a delimiter run and surrounding horizontal whitespace close a fence."""
    return re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}[ \t]*", row) is not None


def opening_fence(row):
    """A fence opens at most three spaces in; a backtick fence's info text has no backtick."""
    match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", row)
    if not match or (match[1][0] == "`" and "`" in match[2]):
        return None
    return match[1][0], len(match[1])


def rule_lines(text):
    """Annotate physical lines with their source sections."""
    rows, headings, fence = [], [], None
    for raw in re.findall(r"[^\n]*\n|[^\n]+$", text):
        row = raw.rstrip("\r\n")
        opening = re.match(r"^[ \t]*(?:(?:[-+*]|\d+[.)])[ \t]+)?(`{3,}|~{3,})", row)
        if fence:
            if closing_fence(row, fence):
                fence = None
        elif opening:
            fence = opening[1][0], len(opening[1])
        else:
            heading = re.match(r"^ {0,3}(#{1,6})\s+(.+?)(?:\s+#+)?\s*$", row)
            if heading:
                level = len(heading[1])
                while headings and headings[-1][0] >= level:
                    headings.pop()
                headings.append((level, heading[2]))
        rows.append(dict(raw=raw, section=" / ".join(title for _, title in headings) or "(root)"))
    return rows


def rule_changes(repo, base, head):
    """Report every Git zero-context block, including compact same-word rewraps."""
    policy, patterns = rule_policy(repo, base)
    provenance_patterns = [rule_glob(pattern) for pattern in (*RULE_PROVENANCE_PATHS,
                                                             *policy["extra_provenance_paths"])]
    records = git(repo, "diff", "--no-color", "--raw", "--no-abbrev", "--no-ext-diff", "--no-textconv", "--no-renames", "-z",
                  base, head).split("\0")
    changes, provenance = [], []
    for metadata, path in zip(records[::2], records[1::2]):
        if path.startswith("docs/") or not any(pattern.fullmatch(path) for pattern in patterns):
            continue
        old_mode, new_mode, _, _, _ = metadata[1:].split()
        before = rule_blob(repo, base, path, old_mode) if old_mode != "000000" else ""
        after = rule_blob(repo, head, path, new_mode) if new_mode != "000000" else ""
        old_rows, new_rows = rule_lines(before), rule_lines(after)
        patch = git(repo, "--literal-pathspecs", "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames",
                    "--text", "--diff-algorithm=myers", "--no-indent-heuristic", "--inter-hunk-context=0",
                    "-U0", base, head, "--", path)
        is_provenance = any(pattern.fullmatch(path) for pattern in provenance_patterns)
        for hunk in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", patch, re.M):
            sides = []
            for rows, line, count in ((old_rows, int(hunk[1]), int(hunk[2] or 1)),
                                      (new_rows, int(hunk[3]), int(hunk[4] or 1))):
                selected = rows[line - 1:line - 1 + count] if count else []
                sides.append(dict(path=path, line=line, end_line=line + count - 1,
                                  section=selected[0]["section"], text="".join(row["raw"] for row in selected))
                             if selected else None)
            old, new = sides
            if is_provenance:
                # Approval evidence never pairs, even within one changed block.
                provenance.extend(dict(kind=kind, old=old if kind == "removed" else None,
                                       new=new if kind == "added" else None, provenance=True)
                                  for kind, side in (("removed", old), ("added", new)) if side)
            else:
                kind = "changed" if old and new else "removed" if old else "added"
                if old and new:
                    old_lines, new_lines = ([line.strip() for line in side["text"].removesuffix("\n").split("\n")]
                                            for side in (old, new))
                    if old_lines != new_lines and " ".join(old_lines) == " ".join(new_lines):
                        kind = "rewrapped"
                changes.append(dict(kind=kind, old=old, new=new))
    # Exact copies only, with FIFO source order for repeated copies. No all-pairs work.
    additions = defaultdict(deque)
    for index, change in enumerate(changes):
        if change["kind"] == "added":
            additions[change["new"]["text"]].append(index)
    paired = set()
    for change in changes:
        if change["kind"] == "removed" and additions[change["old"]["text"]]:
            index = additions[change["old"]["text"]].popleft()
            change.update(kind="moved", new=changes[index]["new"])
            paired.add(index)
    changes = [change for index, change in enumerate(changes) if index not in paired]
    return changes + provenance, policy, base


def declared_rule_changes(body):
    """Find the declaration section by whole lines, outside fences and whole-line comments.

    Line-based by design: inline comments and code spans are not parsed. The declaration is
    advisory (every reported item needs a disposition), so a rare miss or extra match costs
    one warning line, not hidden evidence."""
    lines = body.splitlines()
    start, fence, comment = None, None, False
    for index, line in enumerate(lines):
        if fence:
            if closing_fence(line, fence):
                fence = None
            continue
        if comment:
            comment = "-->" not in line
            continue
        if re.match(r"^ {0,3}<!--", line):
            comment = "-->" not in line[line.index("<!--") + 4:]
            continue
        opening = opening_fence(line)
        if opening:
            fence = opening
            continue
        if start is None:
            if re.fullmatch(r" {0,3}##[ \t]+Rule changes[ \t]*#*[ \t]*", line):
                start = index
        elif re.match(r"^ {0,3}#{1,2}[ \t]+", line):
            return list(enumerate(lines[start:index], start + 1))
    return list(enumerate(lines[start:], start + 1)) if start is not None else []


def rule_location(unit):
    if unit is None:
        return "(none)"
    # JSON quoting keeps unusual path and heading characters on one unambiguous line.
    location = f'{json.dumps(unit["path"], ensure_ascii=False)}:{unit["line"]} — {json.dumps(unit["section"], ensure_ascii=False)}'
    if unit.get("end_line", unit["line"]) > unit["line"]:
        location += f'; through line {unit["end_line"]}'
    return location


def render_rule_report(parts, policy, out, index):
    """Check the sole allowance before joining the complete rendered report."""
    if sum(len(display(part)) for part in parts) + len(parts) - 1 > policy["max_report_chars"]:
        raise RuleReportTooLarge("\n".join([*out, "", "FAILED CLOSED: complete rule report exceeds "
                                         f"{policy['max_report_chars']} characters; full text withheld, every location follows.",
                                         *index]) + "\n")
    return "\n".join(parts)


def rule_report(changes, policy, base, head, declaration_text, declaration_source):
    declared = declared_rule_changes(declaration_text)
    declaration_heading = f"### Declared changes ({declaration_source} line numbers)"
    if not changes:
        parts = ["No protected rule text changed."]
        if declared:
            parts.extend(["", declaration_heading, *(f"{number}: {line}" for number, line in declared)])
        return render_rule_report(parts, policy, parts, [])
    out = ["## Rule text changes", f"Base: `{base}`; head: `{head}`",
           "; ".join(f"{kind}: {sum(item['kind'] == kind and not item.get('provenance') for item in changes)}"
                     for kind in ("removed", "added", "changed", "moved", "rewrapped"))]
    out.append(f"Provenance entries: {sum(bool(item.get('provenance')) for item in changes)}")
    if not declared:
        out.append(f"UNDECLARED RULE CHANGES: {declaration_source} has no ## Rule changes section. Blocking.")
    out.extend(["", declaration_heading])
    out.extend([f"{number}: {line}" for number, line in declared] or ["(none)"])
    index = [f"- RC{number} rewrapped: {rule_location(item['old'])} → {rule_location(item['new'])}; same words, line breaks moved"
             if item["kind"] == "rewrapped" else
             f"- RC{number} {'provenance ' if item.get('provenance') else ''}{item['kind']}: old {rule_location(item['old'])}; new {rule_location(item['new'])}"
             for number, item in enumerate(changes, 1)]
    detail = []
    provenance_started = False
    for number, item in enumerate(changes, 1):
        if item["kind"] == "rewrapped":
            continue  # The location index is the complete one-line rendering.
        if item.get("provenance") and not provenance_started:
            detail.extend(["", "### Provenance entries"])
            provenance_started = True
        heading = "####" if item.get("provenance") else "###"
        detail.extend(["", f"{heading} RC{number} {item['kind']}"])
        for side in ("old", "new"):
            unit = item[side]
            value = unit["text"] if unit else "(none)"
            fence = "`" * max(3, max((len(m[0]) + 1 for m in re.finditer(r"`+", value)), default=3))
            detail.extend([f"{side.title()}: {rule_location(unit)}", fence + "text", value, fence])
    parts = [*out, "", "### Item locations", *index, *detail]
    return render_rule_report(parts, policy, out, index)



def noninteractive_env():
    return dict(os.environ, GIT_TERMINAL_PROMPT="0", GH_PROMPT_DISABLED="1", GIT_NO_REPLACE_OBJECTS="1")


def display(text):
    """Keep undecodable bytes visible without changing paths passed back to Git."""
    return redact(text.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="backslashreplace")).replace("\0", r"\x00")


def run(repo, *args, input=None):
    result = subprocess.run(args, cwd=repo, env=noninteractive_env(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=None if input is not None else subprocess.DEVNULL,
                            input=input.encode("utf-8") if input is not None else None)
    # Decode bytes ourselves: text mode also rewrites CR/LF inside NUL-delimited paths.
    result.stdout = result.stdout.decode("utf-8", errors="surrogateescape")
    result.stderr = redact(result.stderr.decode("utf-8", errors="surrogateescape"))
    return result


def git(repo, *args, input=None):
    result = run(repo, "git", *args, **({"input": input} if input is not None else {}))
    if result.returncode:
        raise PrepareError(result.stderr.strip() or "git command failed: " + " ".join(args))
    return result.stdout


def resolve_base(repo, explicit=None, no_fetch=False, *, pin=False):
    """Return the chosen ref (or captured commit), remote and merge freshness."""
    remotes = git(repo, "remote").splitlines()
    remote = "upstream" if "upstream" in remotes else "origin" if "origin" in remotes else None
    if explicit:
        selected = next((r for r in remotes if explicit.startswith((r + "/", "refs/remotes/" + r + "/"))), None)
        if not selected or no_fetch:
            commit = git(repo, "rev-parse", "--verify", "--end-of-options", explicit + "^{commit}").strip()
            return commit if pin else explicit, selected or remote, True
        remote = selected
        branch = explicit.removeprefix("refs/remotes/").removeprefix(remote + "/")
        base = explicit
        advertised_ok = True
    else:
        if not remote:
            raise PrepareError("no upstream or origin remote; specify --base REF")
        if no_fetch:
            raise PrepareError("--no-fetch requires --base REF")
        advertised = run(repo, "git", "ls-remote", "--symref", remote, "HEAD", "refs/heads/main", "refs/heads/master")
        advertised_ok = advertised.returncode == 0
        match = re.search(r"^ref: refs/heads/(.+)\s+HEAD$", advertised.stdout, re.M)
        if not advertised_ok:
            cached = run(repo, "git", "symbolic-ref", "--quiet", f"refs/remotes/{remote}/HEAD")
            if cached.returncode:
                raise PrepareError(f"ls-remote {remote} failed and no cached default branch exists; specify --base REF")
            base = cached.stdout.strip().removeprefix("refs/remotes/")
            commit = git(repo, "rev-parse", "--verify", "--end-of-options", base + "^{commit}").strip()
            print(f"warning: ls-remote {remote} failed: {redact(advertised.stderr.strip())}; using cached base {base}; freshness could not be verified", file=sys.stderr)
            return commit if pin else base, remote, False
        branch = match[1] if match else next((b for b in ("main", "master")
                                              if re.search(r"\srefs/heads/" + b + r"$", advertised.stdout, re.M)), None)
        if not branch:
            raise PrepareError("remote advertises no default, main or master branch; specify --base REF")
        base = f"{remote}/{branch}"
    ref = f"refs/remotes/{remote}/{branch}"
    fetched = run(repo, "git", "fetch", remote, f"+refs/heads/{branch}:{ref}")
    if fetched.returncode:
        print(f"warning: fetch {base} failed: {redact(fetched.stderr.strip())}", file=sys.stderr)
    commit = git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").strip()
    if fetched.returncode:
        print(f"warning: using cached base {base}; freshness could not be verified", file=sys.stderr)
    return commit if pin else base, remote, advertised_ok and fetched.returncode == 0


def update(repo, base):
    if git(repo, "status", "--porcelain").strip():
        raise PrepareError("checkout is not clean; commit or stash changes before updating")
    git(repo, "symbolic-ref", "--quiet", "HEAD")
    result = run(repo, "git", "merge", "--no-edit", base)
    if result.returncode:
        conflicts = git(repo, "diff", "--name-only", "--diff-filter=U").strip()
        if conflicts:
            raise PrepareError("merge conflict; merge left in progress. Conflicted files:\n" + conflicts)
        raise PrepareError(result.stderr.strip() or result.stdout.strip())
    print(display(result.stdout.strip()), file=sys.stderr)


def web_remote(repo, remote):
    if not remote:
        return None
    url = git(repo, "remote", "get-url", remote).strip()
    if re.match(r"^[^/@]+@[^:]+:", url):
        url = "https://" + url.split("@", 1)[1].replace(":", "/", 1)
    parsed = urlsplit(url)
    if parsed.hostname not in ("github.com", "gitlab.com"):
        return None
    return "https://" + parsed.hostname + parsed.path.removesuffix(".git").rstrip("/")


def link(url, head, path, line=1):
    label = f"{display(path)}:{line}"
    if not url:
        return label
    route = "/-/blob/" if urlsplit(url).hostname == "gitlab.com" else "/blob/"
    return f"[{label}]({url}{route}{head}/{quote_from_bytes(os.fsencode(path), safe='/')}#L{line})"


def kind(path):
    p = Path(path)
    if "docs" in p.parts or (p.suffix.lower() in (".md", ".rst", ".txt", ".adoc") and p.name != "CMakeLists.txt"):
        return "docs"
    return "test" if TEST.search(path) else "source"


def changed_files(repo, rng):
    # Disabling renames keeps each path unambiguous, including deletions and unusual names.
    records = git(repo, "diff", "--no-renames", "--numstat", "-z", rng).split("\0")
    files = [tuple(record.split("\t", 2)) for record in records if record]
    return sorted(files, key=lambda row: (("source", "test", "docs").index(kind(row[2])), row[2]))


class GitHubUnavailable(Exception):
    def __init__(self, message):
        super().__init__(redact(message))


def gh_json(repo, *args):
    try:
        result = subprocess.run(["gh", *args], cwd=repo, text=True, encoding="utf-8",
                                errors="replace", capture_output=True, timeout=30,
                                env=noninteractive_env(), stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitHubUnavailable(str(exc)) from exc
    if result.returncode:
        if re.search(r"HTTP 404|no pull requests? found", result.stderr, re.I):
            return None
        raise GitHubUnavailable(result.stderr.strip() or "gh failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GitHubUnavailable("invalid gh JSON: " + str(exc)) from exc


def issue_refs(text):
    # Bare numbers require a linking keyword; qualified references and URLs do not.
    # A qualified owner/repo#N stands alone: not inside a path or URL, not an anchor such as #5-implement.
    ref = r"https://github\.com/[\w.-]+/[\w.-]+/issues/\d+|(?<![\w./-])[\w.-]+/[\w.-]+#\d+(?![\w-])"
    pattern = r"(?:" + ref + r")|\b(?:refs|closes|fixes|resolves)\s+((?:#\d+(?:\s*(?:,\s*(?:and\s+)?|and\s+))?)+)"
    found = []
    for match in re.finditer(pattern, text, re.I):
        found.extend(re.findall(r"#\d+", match[1]) if match[1] else [match[0]])
    return found


def issue_location(ref, url):
    match = re.fullmatch(r"https://github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)/?", ref)
    if not match:
        match = re.fullmatch(r"([\w.-]+/[\w.-]+)#(\d+)", ref)
    if match:
        return match[1], match[2]
    if re.fullmatch(r"#?\d+", ref) and url and urlsplit(url).hostname == "github.com":
        return urlsplit(url).path.strip("/"), ref.lstrip("#")
    return None


def api_comments(repo, endpoint):
    pages = gh_json(repo, "api", "--method", "GET", "--paginate", "--slurp",
                    endpoint + "?per_page=100")
    if pages is None:
        raise GitHubUnavailable("comments not found: " + endpoint)
    return [comment for page in pages for comment in page]


def pr_context(repo, args, url, *, linked_issues=True):
    pr, issues, comments, notices, missing = {}, [], [], [], []
    texts = []
    refs = list(args.issue) if linked_issues else []
    pr_link = args.pr or "(none)"
    if args.pr and args.pr.isdigit() and url:
        pr_link = f"{url}/pull/{args.pr}"
    def unavailable(source, exc):
        notices.append(f"GitHub context unavailable for {source}: {exc}")

    def collect_comments(endpoint):
        try:
            comments.extend(api_comments(repo, endpoint))
        except GitHubUnavailable as exc:
            unavailable(endpoint, exc)

    if not shutil.which("gh"):
        if args.pr or refs:
            raise PrepareError("cannot resolve explicitly requested PR/issue: gh is not installed")
        notices.append("GitHub context unavailable; skipped linked issues, maintainer comments and PR description (sources 2–4): gh is not installed")
    else:
        if args.pr or url and urlsplit(url).hostname == "github.com":
            try:
                pr = gh_json(repo, "pr", "view", *([args.pr] if args.pr else []),
                             "--json", "url,title,body") or {}
            except GitHubUnavailable as exc:
                if args.pr:
                    raise PrepareError(f"cannot resolve requested PR {args.pr}: {exc}") from exc
                unavailable("PR description", exc)
            if args.pr and not pr:
                raise PrepareError(f"requested PR not found: {args.pr}")
            pr_link = pr.get("url") or pr_link
            texts.append(pr.get("body") or "")
        # A PR URL determines where bare issue numbers belong, including forks.
        issue_url = pr.get("url", "").split("/pull/")[0] or url
        if linked_issues:
            refs.extend(issue_refs(pr.get("body") or ""))
        seen = set()
        for ref in refs:
            location = issue_location(ref, issue_url)
            if not location or location in seen:
                if not location:
                    if ref in args.issue:
                        raise PrepareError(f"cannot resolve requested issue: {ref}")
                    missing.append(ref)
                continue
            seen.add(location)
            owner_repo, number = location
            endpoint = f"repos/{owner_repo}/issues/{number}"
            try:
                issue = gh_json(repo, "api", "--method", "GET", endpoint)
            except GitHubUnavailable as exc:
                if ref in args.issue:
                    raise PrepareError(f"cannot resolve requested issue {ref}: {exc}") from exc
                unavailable(endpoint, exc)
                continue
            if not issue or "pull_request" in issue:
                if ref in args.issue:
                    raise PrepareError(f"requested issue not found: {ref}")
                missing.append(ref if not ref.isdigit() else "#" + ref)
                continue
            issues.append(issue)
            texts.append(issue.get("body") or "")
            collect_comments(endpoint + "/comments")
        if pr.get("url"):
            match = re.fullmatch(r"https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)", pr["url"])
            if match:
                owner_repo, number = match.groups()
                for endpoint in (f"issues/{number}/comments", f"pulls/{number}/comments", f"pulls/{number}/reviews"):
                    collect_comments(f"repos/{owner_repo}/{endpoint}")
    comments = [c for c in comments if c.get("author_association") in {"OWNER", "MEMBER", "COLLABORATOR"}
                and (c.get("user") or {}).get("type", "").lower() != "bot"
                and not (c.get("user") or {}).get("login", "").lower().endswith("[bot]")
                and c.get("body")]
    for comment in comments:
        if not (comment.get("user") or {}).get("login"):
            notices.append(f"Maintainer author unknown: {comment.get('html_url', '(no URL)')}")
    comments.sort(key=lambda c: (c.get("created_at") or c.get("submitted_at") or "", c.get("html_url", "")))
    return pr, issues, comments, pr_link, texts, missing, notices


def discover_spec(repo, head, explicit, texts, files, missing=None):
    if explicit:
        if "#" in explicit:
            raise PrepareError("spec section selectors are not supported; select a whole document with --spec PATH")
        path = re.sub(r"^(?:\./)+", "", explicit)  # The changed-file inventory never spells a leading "./".
        return path if run(repo, "git", "cat-file", "-e", f"{head}:{path}").returncode == 0 else None
    paths = git(repo, "ls-tree", "-r", "--name-only", "-z", head).split("\0")
    refs = None
    def url_path(match):
        nonlocal refs
        source = match[0].rstrip(".,;")
        try:
            parsed = urlsplit(source)
        except ValueError:
            if missing is not None:
                missing.append(source)
            return " "  # Malformed URLs are not repository path mentions.
        route = None
        host = (parsed.hostname or "").removeprefix("www.")
        if host == "gitlab.com":
            route = re.match(r"/(?:[^/]+/){2,}-/(?:blob|raw)/(.+)", parsed.path)
        elif host == "github.com":
            route = re.match(r"/[^/]+/[^/]+/(?:blob|raw)/(.+)", parsed.path)
        elif host == "bitbucket.org":
            route = re.match(r"/[^/]+/[^/]+/src/(.+)", parsed.path)
        elif host == "raw.githubusercontent.com":
            route = re.match(r"/[^/]+/[^/]+/(.+)", parsed.path)
        if route:
            if refs is None:
                refs = set()
                for ref in git(repo, "for-each-ref", "--format=%(refname)").splitlines():
                    for prefix in ("refs/heads/", "refs/tags/", "refs/remotes/"):
                        if ref.startswith(prefix):
                            name = ref[len(prefix):]
                            refs.add(name.partition("/")[2] if prefix == "refs/remotes/" else name)
            tail = unquote(route[1])
            # The longest known ref wins before inspecting the remaining whole
            # path. Never strip arbitrary directories to find a tracked suffix.
            ref = max((ref for ref in refs if tail.startswith(ref + "/")), key=len,
                      default=tail.partition("/")[0])
            path = tail[len(ref) + 1:]
            if path in paths and path.lower().endswith(".md"):
                return " " + path + " "
        if missing is not None and unquote(parsed.path).lower().endswith(".md"):
            missing.append(source)
        # Do not let an unrecognized URL match a repository-path suffix.
        return " "

    texts = [re.sub(r"https?://[^\s<>\"'`)]+", url_path, text) for text in texts]
    # Explicit Design lines outrank ordinary path mentions across all sources.
    for text in texts:
        for design in re.finditer(r"^Design:\s+(\S+?)(?:\s+\[[^\]]*\])?\s*$", text, re.M):
            path = re.sub(r"^(?:\./|/)", "", design[1])
            if path in paths:
                return path
    for text in texts:
        named = [(match.start(), path) for path in paths if path.lower().endswith(".md")
                 for match in [re.search(r"(?<![^\s`\"'(<\[*])(?:\./|/)?" + re.escape(path) + r"(?=\.(?:$|\s)|$|[\s`\"')>\]#,:;*])", text)] if match]
        if named:
            return min(named)[1]
    edited = [path for _, _, path in files if path in paths and path.lower().endswith(".md")
              and any(re.search(r"(?:^|[-_.])(design|spec|specs)(?:$|[-_.])", part, re.I)
                      for part in Path(path).parts)]
    return min(edited) if edited else None


def requirement_entries(repo, args, pr, issues, comments, texts, commits, files, url, head, missing, notices,
                        documentation=False, check=False):
    entries = []
    def add(category, source, source_link, body, **extra):
        entries.append(dict(category=category, source=source, link=source_link, body=body, **extra))
    if check:
        # A check round leaves specifications and issues in the checkout; it keeps human comments and the PR description.
        return [*comment_entries(comments, notices), *pr_entries(pr), *([] if pr else commit_entries(repo, commits, url))]
    reference_text = "\n".join([*texts, *(body for _, body in commits)])
    tests = list(dict.fromkeys([*[t.strip() for t in (args.tests or "").split(",") if t.strip()],
                              *re.findall(r"(?<![A-Za-z0-9_-])" + re.escape(args.test_prefix) + r"\d+(?![A-Za-z0-9_-])", reference_text)]))
    if documentation and (args.spec or args.tests):
        raise PrepareError("registered specifications use --assignment sections and required_test_reviews, not --spec or --tests")
    path = None if documentation else discover_spec(repo, head, args.spec, [*texts, *(body for _, body in commits)], files, missing)
    doc = None
    if args.spec and not path:
        missing.append(args.spec)
    if path:
        object_name = f"{head}:{path}"
        size = int(git(repo, "cat-file", "-s", object_name).strip())
        if size > SPEC_LIMIT:
            raise PrepareError(f"Spec {path}: {size:,} bytes exceeds document limit {SPEC_LIMIT:,} bytes; select a smaller document.")
        result = run(repo, "git", "show", object_name)
        if result.returncode:
            missing.append(path)
        else:
            doc = result.stdout
    if doc is None and not documentation:
        missing.extend(tests)
    elif doc is not None:
        source_link = link(url, head, path) if url else f"[{path}:1]({quote_from_bytes(os.fsencode(path), safe='/')}#L1)"
        add("spec", f"Design/spec {path} — Full document", source_link, doc, path=path)
        for test in tests:
            if not any(row.lstrip().startswith("|") and re.search(
                r"(?<![A-Za-z0-9_-])" + re.escape(test) + r"(?![A-Za-z0-9_-])", row.split("|")[1]
            ) for row in doc.splitlines()):
                missing.append(test)
    for issue in issues:
        labels = ", ".join(label["name"] for label in issue.get("labels", [])) or "(none)"
        add("issue", f"Issue #{issue['number']}: {issue['title']} (labels: {labels})",
            issue["html_url"], issue.get("body") or "")
    entries.extend([*comment_entries(comments, notices), *pr_entries(pr)])
    if not pr and not issues:
        entries.extend(commit_entries(repo, commits, url))
    return entries


def comment_entries(comments, notices):
    entries = []
    for comment in comments:
        body = comment["body"]
        source = f"Maintainer comment by {(comment.get('user') or {}).get('login') or 'unknown'} ({comment['author_association']})"
        if len(body) > COMMENT_LIMIT:
            notices.append(f"Comment capped at {COMMENT_LIMIT:,} characters: {comment['html_url']}")
            body = body[:COMMENT_LIMIT] + "\n[Comment cut at character cap.]"
        entries.append(dict(category="comment", source=source, link=comment["html_url"], body=body))
    return entries


def commit_entries(repo, commits, url):
    return [dict(category="commit", source="Commit message " + sha[:12], body=body,
                 link=f"{url}/commit/{sha}" if url else f"[local checkout]({quote(str(repo), safe='/')}) (`git show {sha}`)")
            for sha, body in commits]


def pr_entries(pr):
    return [dict(category="pr", source="PR description (author claims): " + pr["title"], link=pr["url"],
                 body=pr.get("body") or "")] if pr else []


def requirements_part(entries, mode, shown=None):
    """A specification that the change part shows whole is a pointer, so its text appears once.

    shown maps a raw Git path to the number of the changed file shown whole."""
    out = ["# 4. Requirements", "", "## Index"]
    for n, entry in enumerate(entries, 1):
        out.append(f"- R{n}. {entry['source']} — {entry['link']}")
    if not entries:
        out.append("(No requirements found.)")
    for n, entry in enumerate(entries, 1):
        if mode == "diff" and entry["category"] == "spec":
            continue
        body = entry["body"]
        number = (shown or {}).get(entry["path"]) if entry["category"] == "spec" else None
        if number:
            body = (f"Its full text at the reviewed head is changed file {number} in part 5, "
                    "shown whole with its changes marked.")
        out.extend(["", f"## R{n}. {entry['source']}", body])
    return "\n".join(out)


class DiffTooLarge(Exception):
    pass


def file_diff(repo, rng, path, mode, budget, context=None):
    """Bound every read, including a single enormous source line."""
    unified = ("-U0" if mode == "pack" else f"-U{context}" if context is not None
               else "-U3" if kind(path) == "test" else "-U10")
    # Short submodule lines need no commits from the submodule itself; blank context keeps its space.
    command = ["git", "-c", "diff.submodule=short", "-c", "diff.suppressBlankEmpty=false", "diff", "--no-ext-diff",
               "--no-textconv", "--no-renames", "--no-color", unified, rng, "--", ":(literal)" + path]
    env = noninteractive_env()
    env.pop("GIT_DIFF_OPTS", None)  # The explicit context argument decides the context.
    with tempfile.TemporaryFile() as errors, subprocess.Popen(
        command, cwd=repo, stdout=subprocess.PIPE, stderr=errors,
        env=env, stdin=subprocess.DEVNULL
    ) as process:
        try:
            if mode == "pack":
                hunks, size, continuation = [], 0, False
                while chunk := process.stdout.readline(8192):
                    if not continuation and chunk.startswith(b"@@"):
                        header = chunk.decode("utf-8", errors="backslashreplace").rstrip()
                        if not chunk.endswith(b"\n"):
                            header += " [Hunk header cut at 8192 bytes.]"
                        size += len(header) + 1
                        if size > budget:
                            raise PrepareError(f"hunk headers exceed the change budget for {path}; narrow the review range")
                        hunks.append(header)
                    continuation = not chunk.endswith(b"\n")
                result = "\n".join(hunks)
            else:
                # The budget counts displayed characters; one character is at most four UTF-8 bytes.
                data = process.stdout.read(4 * max(0, budget) + 1)
                if len(data) > 4 * max(0, budget):
                    raise DiffTooLarge()
                # Decode like every other Git read; display() escapes undecodable bytes when rendering.
                result = data.decode("utf-8", errors="surrogateescape").rstrip("\n")
                if len(display(result)) > budget:
                    raise DiffTooLarge()
            if process.wait():
                errors.seek(0)
                raise PrepareError(errors.read().decode("utf-8", errors="replace").strip() or f"git diff failed for {path}")
            return result
        finally:
            # A bounded structured read may stop early before falling back to pack.
            if process.poll() is None:
                process.terminate()
            process.stdout.close()


def fenced(text, language=""):
    """Keep arbitrary backtick runs inside their containing code block."""
    fence = "`" * max(3, max((len(m[0]) + 1 for m in re.finditer(r"`+", text)), default=3))
    return "\n".join((fence + language, text, fence))


def grouped(number):
    """ISO 80000-1 digit grouping for sizes in prompt text."""
    return f"{number:,}".replace(",", " ")


def head_text(repo, head, path, full_file_cap, budget):
    """Return a changed file's head text when it can be shown whole, else why it cannot."""
    entry = git(repo, "ls-tree", "-z", head, "--", ":(literal)" + path)
    object_type = entry.split(" ", 2)[1] if entry else None
    if object_type == "commit":
        return None, "submodule"
    if object_type != "blob":
        return None, "deleted"
    size = int(git(repo, "cat-file", "-s", f"{head}:{path}"))
    if size > full_file_cap * 4:
        return None, f"{grouped(size)} bytes"
    if size > max(0, budget) * 4:
        raise DiffTooLarge()  # Checked before the read: the text cannot fit what remains.
    text = git(repo, "show", f"{head}:{path}")
    if "\0" in text:
        return None, "binary"
    if len(text) > full_file_cap:
        return None, f"{grouped(len(text))} characters"
    return text, None


def numbered(diff, text):
    """Number Git's whole-file diff: head numbers for context and "+", old numbers for "-".

    Mode, file-type and missing-newline lines stay as unnumbered rows."""
    rows, old, new, started, hunks = [], 0, 0, False, 0
    for line in diff.split("\n"):
        hunk = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", line)
        if hunk:
            old, new, started = int(hunk[1]), int(hunk[2]), True
            hunks += 1
        elif line.startswith("diff --git "):
            started = False  # A type change has a second section with its own headers.
        elif not started:
            if line and not line.startswith(("index ", "--- ", "+++ ")):
                rows.append(line)
        elif line.startswith("\\"):
            rows.append(line)
        elif line[:1] == "-":
            rows.append(f"-{old:>6}\t{line[1:]}")
            old += 1
        elif line[:1] == "+":
            rows.append(f"+{new:>6}\t{line[1:]}")
            new += 1
        else:
            rows.append(f" {new:>6}\t{line[1:]}")
            old += 1
            new += 1
    if hunks:
        lines = text.split("\n")
        if lines[-1] == "":
            lines.pop()
        if [row.split("\t", 1)[1] for row in rows if row[:1] in (" ", "+")] != lines:
            raise PrepareError("git diff did not return the whole file; a file shown whole must rebuild its head text")
        return "\n".join(rows)
    if re.search(r"(?m)^Binary files ", diff):
        return None
    # No content change (for example a mode change): the head text is all context.
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return "\n".join([*rows, *(f" {n:>6}\t{row}" for n, row in enumerate(lines, 1))])


class ChangePart(str):
    """Rendered change text with the file numbers of the files it shows whole, keyed by raw Git path."""

    def __new__(cls, text, shown):
        part = super().__new__(cls, text)
        part.shown = shown
        return part


def structured_change(repo, rng, files, head, budget, full_file_cap):
    """Show each changed text file up to the cap whole, as numbered Git diff output; others as a 3-line diff."""
    base = rng.split("..", 1)[0]
    whole, diff_only, sections, size, shown = [], [], [], 0, {}
    for n, (_, _, path) in enumerate(files, 1):
        if LOCK.search(path):
            continue
        text, reason = head_text(repo, head, path, full_file_cap, budget - size)
        if text is not None:
            lines = text.count("\n") + 1
            rows = numbered(file_diff(repo, rng, path, "diff", max(0, budget - size), context=lines), text)
            if rows is None:
                reason = "binary"
        if reason is None:
            shown[path] = f"F{n}"
            whole.append(f"- F{n} {display(path)}")
            section = "\n\n".join([f"## F{n}. {display(path)} (shown whole)",
                                    f"$ git diff -U<all> {base[:12]} {head[:12]} -- {display(path)}   "
                                    '(line numbers added: new for context and "+", old for "-")',
                                    fenced(rows, "diff")])
        else:
            diff_only.append(f"- F{n} {display(path)} ({reason})")
            diff = file_diff(repo, rng, path, "diff", max(0, budget - size), context=3)
            section = "\n\n".join([f"## F{n}. {display(path)} (diff only, {reason})",
                                    f"$ git diff -U3 {base[:12]} {head[:12]} -- {display(path)}",
                                    fenced(diff, "diff")])
        sections.append(section)
        size += len(display(section)) + 2
        if size > budget:
            raise DiffTooLarge()
    lists = "\n".join(["Files shown whole below, every line numbered, changes marked in place "
                       "(do not open or print them again):", *(whole or ["- none"]), "",
                       "Files shown as a diff only, 3 lines of context (read their other lines in the checkout):",
                       *(diff_only or ["- none"])])
    result = "\n\n".join([lists, *sections])
    if len(display(result)) > budget:
        raise DiffTooLarge()
    return ChangePart(result, shown)


def change_part(repo, rng, files, url, head, mode, budget=None, full_file_cap=FULL_FILE_CAP):
    budget = CODEX_LIMIT if budget is None else max(0, budget)
    if mode != "pack" and sum(int(v) for row in files if not LOCK.search(row[2])
                              for v in row[:2] if v.isdigit()) > budget:
        raise DiffTooLarge()
    out = ["# 5. Change", f"Range: `{rng}`", "", "## Index"]
    for n, (added, removed, path) in enumerate(files, 1):
        note = " (lockfile: listed only)" if LOCK.search(path) else ""
        out.append(f"- F{n}. {display(path)} — {kind(path)} +{added}/-{removed} — {link(url, head, path)}{note}")
    size = sum(len(line) + 1 for line in out)
    if mode == "structured":
        part = structured_change(repo, rng, files, head, max(0, budget - size), full_file_cap)
        out.extend(["", part])
        return ChangePart("\n".join(out), part.shown)
    for n, (_, _, path) in enumerate(files, 1):
        if LOCK.search(path):
            continue
        diff = file_diff(repo, rng, path, mode, max(0, budget - size))
        header = f"## F{n}. {display(path)}"
        out.extend(["", header])
        if mode == "pack":
            body = ["Touched functions (hunk headers):", diff or "(No textual hunks.)"]
        else:
            fence = "`" * max(3, max((len(m[0]) + 1 for m in re.finditer(r"`+", diff)), default=3))
            body = [fence + "diff", diff, fence]
        out.extend(body)
        size += len(header) + 2 + sum(len(line) + 1 for line in body)
        if mode != "pack" and size > budget:
            raise DiffTooLarge()
    return "\n".join(out)


def lens_settings(name, config=None):
    """Read a lens's family and read-only sandbox from the panel's plain config."""
    config = Path(config) if config is not None else HERE / "review-panel.lenses"
    settings = {}
    try:
        for number, line in enumerate(config.read_text().splitlines(), 1):
            if not line.strip():
                continue
            match = re.fullmatch(r"([a-z0-9-]+)\s+([abc])\s+(read-only)", line.strip())
            if not match:
                raise PrepareError(f"invalid lens config: {config}:{number}; expected name family read-only")
            lens, family, sandbox = match.groups()
            if lens in settings:
                raise PrepareError(f"duplicate lens config: {config}:{number}: {lens}")
            settings[lens] = (family, sandbox)
    except (OSError, UnicodeError) as exc:
        raise PrepareError(f"cannot read lens config {config}: {exc}") from exc
    if name not in settings:
        raise PrepareError(f"lens not configured: {name} in {config}")
    return settings[name]


def review(repo, args, base, remote, head=None, *, documentation_prepared=False):
    if head is None:
        head = git(repo, "rev-parse", "--verify", "--end-of-options",
                   (getattr(args, "rev", None) or "HEAD") + "^{commit}").strip()
    base = git(repo, "merge-base", base, head).strip()
    rng = f"{base}..{head}"
    # A check round reviews only the fix: the change since the last reviewed commit.
    since = getattr(args, "since", None)
    fix_base = git(repo, "rev-parse", "--verify", "--end-of-options", since + "^{commit}").strip() if since else None
    change_base = fix_base or base
    change_rng = f"{change_base}..{head}"
    url = web_remote(repo, remote)
    pr, issues, comments, pr_link, texts, missing, notices = pr_context(repo, args, url, linked_issues=not since)
    log = git(repo, "log", "--reverse", "--format=%H%x00%B%x00", change_rng).split("\0")
    commits = [(log[n].strip(), log[n + 1].strip()) for n in range(0, len(log) - 1, 2)]
    summary = Path(args.summary).read_text() if args.summary else pr.get("title") or "\n".join(body.splitlines()[0] for _, body in commits if body)
    lens = args.lens or {"codex": "generalist-a", "grok": "generalist-b", "kimi": "generalist-c"}[args.cli]
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", lens):
        raise PrepareError("invalid lens name")
    changes, policy, rule_base = rule_changes(repo, change_base, head)
    declaration_text = (pr.get("body") or "") if args.pr else summary if args.summary else ""
    declaration_source = "PR description" if args.pr else "--summary text"
    report = rule_report(changes, policy, rule_base, head, declaration_text, declaration_source)
    context_only = getattr(args, "context_only", False)
    registered = not documentation_prepared and any(
        git(repo, "ls-tree", "--name-only", head, "--", path).strip()
        for path in ("docs/ENTITIES.json", "docs/DOCUMENTS.json"))
    assignment_path = getattr(args, "assignment", None)
    unavailable = getattr(args, "documentation_unavailable", False)
    needs_documentation = not documentation_prepared and not unavailable and (registered or assignment_path)
    context, sections, common, instructions, reservation = None, None, "", "", 0
    if not context_only or needs_documentation:
        reservation_reviewers = []
        if not context_only:
            family = lens_settings(lens)[0]
            if getattr(args, "reviewers", None):
                reservation_reviewers = [reviewer for reviewer in set([lens, *args.reviewers])
                                         if lens_settings(reviewer)[0] == family]
        # Compilation stays with its owner. The standalone reporting path never
        # imports a sibling, and context-only legacy preparation needs none.
        # Without an explicit assignment, review derives one from changes since the merge base.
        request = dict(repo=str(repo), head=head, base=change_base, lens=lens, full=not context_only, check=bool(since),
                       reviewers=getattr(args, "reviewers", None),
                       reservation_reviewers=reservation_reviewers,
                       documentation=bool(needs_documentation), derive=not assignment_path,
                       assignment=str(Path(assignment_path).resolve()) if assignment_path else None)
        compiled = run(repo, sys.executable, "-I", "-B", str(HERE / "prompt.py"),
                       "--preparer-context", json.dumps(request))
        if compiled.returncode:
            raise PrepareError(compiled.stderr.strip() or "review compiler failed")
        try:
            result = json.loads(compiled.stdout)
            common, instructions, context = result["common"], result["instructions"], result["documentation"]
            sections = result.get("sections")
            reservation = result.get("reservation", 0)
        except (ValueError, KeyError, TypeError) as exc:
            raise PrepareError("invalid review compiler response") from exc
    mode = args.format or ("structured" if args.cli == "codex" else "pack")
    full_file_cap = getattr(args, "full_file_cap", FULL_FILE_CAP)
    if full_file_cap < 0:
        raise PrepareError("--full-file-cap must be nonnegative")
    parts = ["# 1. Review pack\n" + common, "# 2. Instructions\n" + instructions,
             "\n".join(["# 3. Pull request and issue", f"Pull request: {pr_link}",
                        f"Title: {pr.get('title') or git(repo, 'log', '-1', '--format=%s', head).strip()}",
                        "Issues: " + (", ".join(i["html_url"] for i in issues) or "(none)"),
                        f"Range: `{rng}`; head: `{head}`",
                        *([f"Check round: part 5 shows only the fix since the last reviewed head, `{change_rng}`. "
                           f"The whole change `{rng}`, the requirements and all other code stay in the checkout."]
                          if since else []), "", summary])]
    if context_only:
        parts = [f"The checkout under review is {repo}; read its files by absolute path.", *parts[2:]]
    lens_parts = []
    if mode == "structured":
        if not context_only:
            parts.pop(1)
        lens_parts = ["# 7. Lens instructions\n" + instructions]
    if context is not None:
        parts.append(context)
    elif needs_documentation and not assignment_path:
        parts.append("No registered documentation changed in this range.")
    elif unavailable:
        parts.append(f"Registered documentation context was not prepared: {unavailable}. "
                     "Review changed documentation from the diff.")
    parts.append(report)
    files = changed_files(repo, change_rng)
    entries = requirement_entries(repo, args, pr, issues, comments, texts, commits, files, url, head, missing, notices,
                                  documentation=documentation_prepared or bool(needs_documentation), check=bool(since))
    if missing:
        notices.insert(0, "not found: " + ", ".join(dict.fromkeys(missing)))
    # Budget a changed spec that the structured change will show whole as its pointer; its body is the head text.
    predicted = {}
    if mode == "structured":
        numbers = {path: f"F{n}" for n, (_, _, path) in enumerate(files, 1) if not LOCK.search(path)}
        predicted = {entry["path"]: numbers[entry["path"]] for entry in entries
                     if entry["category"] == "spec" and entry["path"] in numbers
                     and "\0" not in entry["body"] and len(entry["body"]) <= full_file_cap}
    # Numstat is already collected; the remaining budget bounds structured reads
    # before constructing a prompt. Pack streams bodies without retaining them.
    # Normalize before trimming: escaping invalid bytes can quadruple their size.
    # A spec keeps its raw path: distinct Git paths can display alike.
    for entry in entries:
        entry.update((key, display(value)) for key, value in entry.items() if key != "path")
    compiled_chars = getattr(args, "compiled_chars", 0)
    if compiled_chars < 0 or (compiled_chars and not context_only):
        raise PrepareError("--compiled-chars requires context-only mode and a nonnegative count")
    limit = CODEX_LIMIT - compiled_chars - reservation
    if args.cli == "codex" and context is not None and getattr(args, "assignment", None) is None:
        mandatory_size = len(display(context))
        if mandatory_size > limit:
            raise PrepareError(f"Size guard: limit {CODEX_LIMIT:,} characters; mandatory documentation requires {mandatory_size:,} characters.\n"
                               "Documentation sections: " + ", ".join(sections or []))
    overhead = len(display("\n\n".join([*notices, *parts, requirements_part(entries, mode, predicted), *lens_parts]))) + 3
    budget = max(0, limit - overhead) if args.cli == "codex" else CODEX_LIMIT
    packed = mode == "pack"
    try:
        change = change_part(repo, change_rng, files, url, head, mode, budget if mode != "pack" else None,
                             full_file_cap=full_file_cap)
    except DiffTooLarge:
        packed = True
        notices.append(PACK_NOTICE)
        change = change_part(repo, change_rng, files, url, head, "pack")
    trimmed = []
    def trim_notes():
        return [f"Size guard: trimmed R{n + 1} ({entries[n]['category']}): {entries[n]['source']}" for n in trimmed]
    def render():
        # Include the terminating newline; main writes this exact representation.
        return display("\n\n".join([*notices, *trim_notes(), *parts, requirements_part(entries, mode, getattr(change, "shown", None)), change,
                                     *lens_parts])) + "\n"
    result = render()
    if args.cli == "codex" and len(result) > limit:
        if not packed:
            notices.append(PACK_NOTICE)
            change = change_part(repo, change_rng, files, url, head, "pack")
            packed = True
            result = render()
        for category in ("comment", "issue", "spec"):
            candidates = sorted((n for n, e in enumerate(entries) if e["category"] == category
                                 and e["body"] and not (mode == "diff" and category == "spec")),
                                key=lambda n: len(entries[n]["body"]), reverse=True)
            for n in candidates:
                if len(result) <= limit:
                    break
                trimmed.append(n)
                # Include the trim notice in the budget before retaining a prefix.
                result = render()
                keep = max(0, len(entries[n]["body"]) - (len(result) - limit) - 64)
                entries[n]["body"] = entries[n]["body"][:keep] + "\n[Trimmed by size guard.]"
                result = render()
        if len(result) > limit:
            history = "\n".join(trim_notes() or ["No requirement bodies eligible for trimming."])
            if context is not None and getattr(args, "assignment", None) is None:
                history += "\nDocumentation sections: " + ", ".join(sections or [])
            raise PrepareError(
                f"Size guard: limit {CODEX_LIMIT:,} characters; final size {len(result) + compiled_chars:,} characters after trimming. "
                "Retained indexes, rules, task and author claims require a smaller input.\n"
                "Already trimmed: change part uses pack (hunk headers).\n" + history)
    if lens in STRUCTURED_ONLY and not context_only and not isinstance(change, ChangePart):
        raise PrepareError(f"the {lens} reviewer runs no commands and needs the structured change part; "
                           "this change is shown as hunk headers only")
    return result


def shows_structured_change(context, cli):
    """Whether a context the panel prepared for this CLI shows the structured change part."""
    return cli == "codex" and PACK_NOTICE not in context.split("\n# 3. Pull request and issue\n", 1)[0]


def ownership(repo, remote):
    url = web_remote(repo, remote)
    if not shutil.which("gh") or not url or urlsplit(url).hostname != "github.com":
        return "unknown (GitHub ownership unavailable)"
    script = HERE.parent.parent / "upstream-contribution" / "scripts" / "repo-ownership.sh"
    result = run(repo, "bash", str(script), urlsplit(url).path.strip("/"))
    if result.returncode in (0, 1) and result.stdout.strip():
        return result.stdout.strip()
    print("warning: ownership check failed: " + result.stderr.strip(), file=sys.stderr)
    return "unknown (ownership check failed)"


def brief(repo, args, base, status, update_note):
    rng = f"{base}...HEAD"
    files = changed_files(repo, rng)
    out = ["# " + ("Fixer brief" if args.command == "fix" else "PR-preparation brief"), f"Range: `{rng}`"]
    out.extend(["\n## Branch update", update_note])
    if args.command == "pr":
        out.extend(["\n## Commits", git(repo, "log", "--oneline", f"{base}..HEAD").strip()])
    out.append("\n## Changed files by kind")
    out.extend(f"- {kind(path)}: {display(path)} (+{added}/-{removed})" for added, removed, path in files)
    out.extend(["\n## Local gate",
                "Use the repository's declared gates in AGENTS.md and the rules file it points to, or its CI workflow when none are declared.",
                "Select targeted tests for the changed source and test files above, including every new regression."])
    if args.command == "fix":
        out.extend(["\n## Reviews to address", *args.reviews] if args.reviews else ["\n## Reviews to address", "(none supplied)"])
    else:
        out.extend(["\n## Ownership", status])
        if not status.startswith("owned "):
            out.append("Upstream-contribution checklist: prove on unmodified upstream; sweep existing work and contribution rules; fix, test and review locally; draft for operator approval. Nothing is posted without operator approval.")
    return "\n".join(out)


def main(argv=None, *, documentation_prepared=False):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("review", "fix", "pr", "base"):
        p = sub.add_parser(command)
        p.add_argument("checkout", type=Path)
        p.add_argument("--base")
        p.add_argument("--no-fetch", action="store_true", help="use an already resolved --base without fetching")
        if command == "review":
            p.add_argument("--rev", default="HEAD", help="commit to review; resolved before base preparation")
            p.add_argument("--context-only", action="store_true", help="emit task context for the commit-built pack compiler")
            p.add_argument("--compiled-chars", type=int, default=0, help="characters reserved for compiled parts and task separator")
            p.add_argument("--assignment", type=Path, help="explicit shared-checker documentation assignment JSON")
            p.add_argument("--reviewers", nargs="+", help="complete round reviewer list for shared documentation context")
            for option in ("pr", "spec", "tests", "lens", "summary"):
                p.add_argument("--" + option)
            p.add_argument("--since", help="last reviewed commit; a check round shows only the change since it")
            p.add_argument("--issue", action="append", default=[])
            p.add_argument("--test-prefix", default="PT")
            p.add_argument("--format", choices=("structured", "diff", "pack"))
            p.add_argument("--full-file-cap", type=int, default=FULL_FILE_CAP,
                           help="structured whole-file character cap (default: 85000; larger files are shown as a diff only)")
            p.add_argument("--cli", choices=("codex", "grok", "kimi"), default="codex")
        if command == "fix":
            p.add_argument("--reviews", nargs="+", default=[])
        if command in ("fix", "pr"):
            p.add_argument("--update", action="store_true", help="merge the base even on external or unknown-ownership repositories")
    p = sub.add_parser("rule-lenses", help="print report-required lenses for this review range")
    p.add_argument("checkout", type=Path)
    p.add_argument("--base", required=True)
    p.add_argument("--rev", default="HEAD")
    p.add_argument("--no-fetch", action="store_true")
    p = sub.add_parser("lens", help="print configured lens family and sandbox")
    p.add_argument("name")
    p.add_argument("--config", type=Path)
    p = sub.add_parser("check-prompt", help="check the complete compiled prompt before dispatch")
    p.add_argument("file", type=Path)
    p.add_argument("--cli", choices=("codex", "grok", "kimi"), required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "lens":
            print(" ".join(lens_settings(args.name, args.config)))
            return 0
        if args.command == "check-prompt":
            size = len(args.file.read_bytes().decode("utf-8"))
            if args.cli == "codex" and size > CODEX_LIMIT:
                raise PrepareError(f"Size guard: limit {CODEX_LIMIT:,} characters; complete prompt size {size:,} characters; narrow the review input")
            return 0
        repo = Path(git(args.checkout, "rev-parse", "--show-toplevel").strip())
        head = None
        if args.command in ("review", "rule-lenses"):
            head = git(repo, "rev-parse", "--verify", "--end-of-options", args.rev + "^{commit}").strip()
            interpreter = os.environ.get("REVIEW_PYTHON")
            delegate = False
            if not documentation_prepared and any(
                    git(repo, "ls-tree", "--name-only", head, "--", path).strip()
                    for path in ("docs/ENTITIES.json", "docs/DOCUMENTS.json")):
                delegate = sys.version_info < (3, 11) and bool(interpreter)
                missing_checker = None if delegate else checker_unavailable()
                if missing_checker and getattr(args, "assignment", None):
                    raise PrepareError(f"registered documentation requires the shared checker: {missing_checker}; "
                                       "set REVIEW_PYTHON to the pinned tool environment's Python executable")
                # A service without the checker still reviews the code; the pack says what it lacks.
                args.documentation_unavailable = missing_checker
            if delegate:
                environment = noninteractive_env()
                environment.pop("REVIEW_PYTHON", None)  # A misconfigured interpreter fails instead of recursing.
                result = subprocess.run([interpreter, "-B", str(Path(__file__).resolve()),
                                         *(sys.argv[1:] if argv is None else argv), "--rev", head], env=environment,
                                        stdin=subprocess.DEVNULL, capture_output=True)
                sys.stdout.write(result.stdout.decode("utf-8"))
                sys.stderr.write(redact(result.stderr.decode("utf-8")))
                return result.returncode
        base, remote, fresh = resolve_base(repo, args.base, args.no_fetch,
                                           pin=args.command in ("base", "review", "rule-lenses"))
        print(f"range: {base}...{head or 'HEAD'}", file=sys.stderr)
        if args.command == "rule-lenses":
            base = git(repo, "merge-base", base, head).strip()
            changes, policy, rule_base = rule_changes(repo, base, head)
            rule_report(changes, policy, rule_base, head, "", "--summary text")
            if changes:  # the rule-preservation reviewer alone audits every report item, provenance entries included
                print("rule-preservation")
        elif args.command == "base":
            print(base)
        elif args.command == "review":
            sys.stdout.write(review(repo, args, base, remote, head, documentation_prepared=documentation_prepared))
        else:
            status = ownership(repo, remote)
            if not fresh:
                behind = git(repo, "rev-list", "--count", f"HEAD..{base}").strip()
                update_note = f"{status}: {behind} commit(s) behind cached base {base}. Base merge skipped; ls-remote or fetch failed, so freshness could not be verified (even with --update)."
            elif not status.startswith("owned ") and not args.update:
                behind = git(repo, "rev-list", "--count", f"HEAD..{base}").strip()
                update_note = (f"{status}: {behind} commit(s) behind {base}. Base merge skipped; "
                               "leave the update method to the operator's instruction. --update forces a base merge.")
            else:
                update(repo, base)
                update_note = f"Merged {base} (or already up to date)."
            print(display(brief(repo, args, base, status, update_note)))
        return 0
    except RuleReportTooLarge as exc:
        sys.stdout.write(display(exc.report))
        print(display(f"error: {exc}"), file=sys.stderr)
        return 1
    except (PrepareError, OSError, UnicodeError) as exc:
        print(display(f"error: {exc}"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

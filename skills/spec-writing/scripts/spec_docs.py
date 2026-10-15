#!/usr/bin/env python3
"""Check, project and select specification Markdown from one immutable snapshot."""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass, field
import hashlib
from html.parser import HTMLParser
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import posixpath
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

try:
    from markdown_it import MarkdownIt
except ModuleNotFoundError:
    MarkdownIt = None

TOOL_VERSION = "1"
REFERENCE = Path(__file__).resolve().parent.parent / "references" / "format-contract.json"
PROFILE_PATH = "rules/writing.md"
PROFILE = Path(__file__).resolve().parents[3] / PROFILE_PATH
JSON_PATHS = ("docs/ENTITIES.json", "docs/DOCUMENTS.json")
START = '<!-- spec-docs:navigation document="{document}" -->'
END = '<!-- /spec-docs:navigation -->'
ATTR_START = '# spec-docs:generated'
ATTR_END = '# /spec-docs:generated'


@dataclass(frozen=True, order=True)
class Diagnostic:
    """A deterministic, source-addressed finding."""
    path: str
    line: int
    code: str
    message: str
    severity: str = "error"

    def __str__(self):
        return f"spec-docs: {self.severity} {self.code} {self.path}:{self.line}: {self.message}"


@dataclass
class Diagnostics:
    """Uncapped findings; warnings do not affect success."""
    items: list[Diagnostic] = field(default_factory=list)

    def add(self, code, message, path="docs/DOCUMENTS.json", line=1):
        self.items.append(Diagnostic(path, line, code, message,
                                     "warning" if code.startswith("W") else "error"))

    @property
    def errors(self):
        return [d for d in sorted(set(self.items)) if d.severity == "error"]

    @property
    def warnings(self):
        return [d for d in sorted(set(self.items)) if d.severity == "warning"]

    @property
    def ok(self):
        return not self.errors

    def to_dict(self):
        return {"errors": [asdict(d) for d in self.errors],
                "warnings": [asdict(d) for d in self.warnings], "ok": self.ok}


class SpecDocsError(Exception):
    """Visible failure suitable for callers and command-line diagnostics."""
    def __init__(self, diagnostics, exit_code=1):
        self.diagnostics = diagnostics
        self.exit_code = exit_code
        super().__init__("\n".join(map(str, diagnostics.errors)))


def fail(code, message, path="docs/DOCUMENTS.json", exit_code=1):
    diagnostics = Diagnostics()
    diagnostics.add(code, message, path)
    raise SpecDocsError(diagnostics, exit_code)


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(path):
    return (isinstance(path, str) and bool(path) and "\\" not in path
            and not PurePosixPath(path).is_absolute()
            and not any(p in ("", ".", "..") for p in path.split("/")))


def git(root, *args):
    proc = subprocess.run(["git", "--no-replace-objects", "-C", str(root), *args], capture_output=True)
    if proc.returncode:
        fail("D27", f"cannot read Git snapshot '{root}': {proc.stderr.decode(errors='replace').strip()}",
             str(root), 2)
    return proc.stdout


@dataclass
class Snapshot:
    """Captured bytes and metadata; subsequent operations never read source files."""
    files: dict[str, bytes]
    tracked: set[str]
    problems: dict[str, str] = field(default_factory=dict)
    revision: str | None = None
    fixture: bool = False
    root: Path | None = None

    @classmethod
    def from_mapping(cls, paths, fixture=False):
        return cls({k: v.encode() if isinstance(v, str) else v for k, v in paths.items()},
                   set(paths), fixture=fixture)

    @staticmethod
    def needs_content(path):
        """Only Markdown, metadata and mixed generated attributes need blob bytes.

        The native tree inventory suffices for existence and regular-file checks
        on code and asset links. No unrelated binary is read or retained.
        """
        return path.lower().endswith('.md') or path in (*JSON_PATHS, '.gitattributes')

    @classmethod
    def from_git(cls, root, staged=False, rev=None, fixture=False):
        if staged and rev:
            fail("D02", "unsupported version, unknown field or malformed declaration: conflicting snapshots", exit_code=2)
        root = Path(root).resolve()
        files, problems = {}, {}
        revision = None
        if staged or rev:
            entries = []
            if staged:
                for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
                    if not entry:
                        continue
                    header, raw_path = entry.split(b"\t", 1)
                    mode, oid, stage = header.split()
                    path = raw_path.decode("utf-8")
                    if stage != b"0":
                        problems[path] = "unmerged index entry"
                    entries.append((path, mode, oid))
            else:
                revision = git(root, "rev-parse", "--verify", rev + "^{commit}").decode().strip()
                for entry in git(root, "ls-tree", "-rz", revision).split(b"\0"):
                    if entry:
                        header, raw_path = entry.split(b"\t", 1)
                        mode, _kind, oid = header.split()
                        entries.append((raw_path.decode("utf-8"), mode, oid))
            regular = [(path, oid) for path, mode, oid in entries if mode in (b"100644", b"100755") and cls.needs_content(path)]
            for path, mode, _oid in entries:
                if mode not in (b"100644", b"100755"):
                    problems[path] = "input is not a regular file"
            if regular:
                proc = subprocess.run(["git", "--no-replace-objects", "-C", str(root), "cat-file", "--batch"],
                                      input=b"\n".join(oid for _, oid in regular) + b"\n",
                                      capture_output=True)
                if proc.returncode:
                    fail("D27", "cannot read Git objects: " + proc.stderr.decode(errors="replace"), exit_code=2)
                offset = 0
                for path, _ in regular:
                    end = proc.stdout.index(b"\n", offset)
                    header = proc.stdout[offset:end].split()
                    if len(header) != 3 or header[1] != b"blob":
                        fail("D27", f"cannot read '{path}': not a blob", path, 2)
                    size = int(header[2])
                    files[path] = proc.stdout[end + 1:end + 1 + size]
                    offset = end + size + 2
            tracked = {e[0] for e in entries}
        else:
            tracked = {p.decode() for p in git(root, "ls-files", "-z").split(b"\0") if p}
            paths = tracked | {p.decode() for p in git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if p}
            tracked |= paths
            for path in sorted(paths):
                target = root / path
                try:
                    if not safe_path(path) or any(p.is_symlink() for p in [target, *target.parents] if p != root):
                        problems[path] = "symlink or path escape"
                    elif not target.exists():
                        problems[path] = "missing input"
                    elif not target.is_file():
                        problems[path] = "input is not a regular file"
                    elif cls.needs_content(path):
                        files[path] = target.read_bytes()
                except OSError as exc:
                    problems[path] = str(exc)
        return cls(files, tracked, problems, revision, fixture, root)

    @property
    def digest(self):
        return digest(canonical({p: digest(b) for p, b in sorted(self.files.items())}))


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.bad = False

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs = dict(attrs)
            if set(attrs) != {"id"} or not attrs.get("id"):
                self.bad = True
            else:
                self.ids.append(attrs["id"])


def anchors(text):
    parser = Anchors()
    parser.feed(text)
    return parser.ids, parser.bad


def visible(children):
    return "".join(t.content if t.type in ("text", "code_inline") else
                   "\n" if t.type in ("softbreak", "hardbreak") else
                   visible(t.children or []) if t.type == "image" else ""
                   for t in children or [])


@dataclass
class Link:
    target: str
    label: str
    line: int
    destination: tuple[str, str] | None = None


@dataclass
class Heading:
    title: str
    level: int
    start: int
    end: int
    intro_end: int
    anchor: str | None
    fields: dict[str, tuple[str, list[Link]]] = field(default_factory=dict)


@dataclass
class Markdown:
    path: str
    text: str
    tokens: list
    headings: list[Heading]
    anchors: dict[str, list[int]]
    links: list[Link]
    rows: list[tuple[list, int, list[str]]]
    inline_links: dict[int, list[Link]]
    generated: list[tuple[int, int]]

    def heading_at(self, line):
        return next((h for h in reversed(self.headings) if h.start <= line < h.end), None)

    def intro_at(self, line):
        return next((h for h in reversed(self.headings) if h.start <= line < h.intro_end), None)

    def use_section_at(self, line):
        """Return the level-2 scope, including its deeper subsections and preamble."""
        return next((h for h in reversed(self.headings) if h.level <= 2 and h.start <= line < h.end), None)

    def range_bytes(self, start, end):
        return "".join(self.text.splitlines(keepends=True)[start:end]).encode()


def parse_markdown(path, text, diagnostics):
    tokens = MarkdownIt("commonmark").enable("table").parse(text)
    destinations, links, rows, headings, inline_links, generated = defaultdict(list), [], [], [], {}, []
    lines = text.splitlines(keepends=True)
    region_start = None
    for i, line in enumerate(lines):
        if "<!-- spec-docs:navigation" in line:
            if region_start is not None:
                diagnostics.add("D02", "malformed declaration: nested navigation region", path, i + 1)
            region_start = i
        if END in line:
            if region_start is None:
                diagnostics.add("D02", "malformed declaration: unmatched navigation marker", path, i + 1)
            else:
                generated.append((region_start, i + 1))
                region_start = None
    if region_start is not None:
        diagnostics.add("D02", "malformed declaration: unclosed navigation region", path, region_start + 1)
    in_region = lambda n: any(a <= n < b for a, b in generated)
    row, headers, in_header = None, [], False
    for i, token in enumerate(tokens):
        line = token.map[0] if token.map else 0
        if token.type == "heading_open" and not in_region(line):
            before = lines[line - 1].strip() if line else ""
            ids, bad = anchors(before)
            home_anchor = ids[0] if len(ids) == 1 and not bad and re.fullmatch(r'<a\s+id="[^"<>]+"\s*></a>', before) else None
            headings.append(Heading(visible(tokens[i + 1].children), int(token.tag[1:]),
                                    line, len(lines), len(lines), home_anchor))
        if token.type == "thead_open":
            in_header = True
        elif token.type == "thead_close":
            in_header = False
        if token.type == "tr_open":
            row = []
        if token.type == "inline" and not in_region(line):
            token_links = []
            children = token.children or []
            for j, child in enumerate(children):
                if child.type in ("html_inline",):
                    ids, bad = anchors(child.content)
                    if bad:
                        diagnostics.add("D02", "malformed declaration: anchors require id, never name", path, line + 1)
                    for anchor in ids:
                        destinations[anchor].append(line)
                if child.type == "image":
                    links.append(Link(child.attrGet("src") or "", visible(child.children), line))
                if child.type == "link_open":
                    end = next((k for k in range(j + 1, len(children)) if children[k].type == "link_close"), len(children))
                    link = Link(child.attrGet("href") or "", visible(children[j + 1:end]), line)
                    links.append(link)
                    token_links.append(link)
            inline_links[id(token)] = token_links
            if row is not None:
                row.append(token)
        if token.type == "html_block" and not in_region(line):
            ids, bad = anchors(token.content)
            if bad:
                diagnostics.add("D02", "malformed declaration: anchors require id, never name", path, line + 1)
            for anchor in ids:
                destinations[anchor].append(line)
        if token.type == "tr_close" and row is not None:
            row_line = row[0].map[0] if row else line
            if in_header:
                headers = [visible(t.children) for t in row]
            else:
                rows.append((row, row_line, headers[:]))
            row = None
    for i, heading in enumerate(headings):
        heading.intro_end = headings[i + 1].start if i + 1 < len(headings) else len(lines)
        for following in headings[i + 1:]:
            if following.level <= heading.level:
                heading.end = following.start - (1 if following.anchor else 0)
                break
        for token in tokens:
            if token.type == "inline" and token.map and not in_region(token.map[0]) and heading.start < token.map[0] < heading.intro_end:
                match = re.match(r"^\*\*([^*]+?):\*\*\s*(.*)", token.content, re.S)
                if match:
                    key = match[1]
                    if key == "Entities in this example":
                        continue  # Adjacent links annotate each block; they are not declaration fields.
                    if key in heading.fields:
                        diagnostics.add("D02", f"malformed declaration: duplicate field '{key}'", path, token.map[0] + 1)
                    heading.fields[key] = (visible(token.children).split(":", 1)[-1].strip(), inline_links.get(id(token), []))
    for identity, positions in destinations.items():
        if len(positions) > 1:
            diagnostics.add("D03", f"duplicate identity '{identity}'; first at {path}:{positions[0] + 1}", path, positions[1] + 1)
    return Markdown(path, text, tokens, headings, dict(destinations), links, rows, inline_links, generated)


@dataclass
class Corpus:
    """Single parsed model shared by all operations."""
    source: Snapshot
    contract: dict
    diagnostics: Diagnostics
    index: dict = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)
    markdown: dict[str, Markdown] = field(default_factory=dict)
    inventory: dict[str, str] = field(default_factory=dict)
    documents: dict[str, dict] = field(default_factory=dict)
    sections: dict[str, dict] = field(default_factory=dict)
    entities: dict[str, dict] = field(default_factory=dict)
    facts: dict[str, dict] = field(default_factory=dict)
    declarations: dict[str, dict] = field(default_factory=dict)
    profile: dict = field(default_factory=dict)
    profile_bytes: bytes = b""
    assignment: dict | None = None
    base: Corpus | None = None

    @property
    def registry(self):
        return {"version": 1, "entities": self.entities}

    @property
    def registry_digest(self):
        return digest(canonical(self.registry))

    def locate(self, selector):
        if not isinstance(selector, str):
            return None
        if selector in self.sections:
            s = self.sections[selector]
            return s["path"], s["heading"]
        if isinstance(selector, str) and "#" in selector:
            doc, anchor = selector.split("#", 1)
            if doc in self.documents:
                matches = [(s["path"], h) for s in self.sections.values() if s["document"] == doc
                           for h in self.markdown.get(s["path"], Markdown("", "", [], [], {}, [], [], {}, [])).headings
                           if h.anchor == anchor and s["heading"].start <= h.start < s["heading"].end]
                unique = {(p, h.start): (p, h) for p, h in matches}
                if len(unique) == 1:
                    return next(iter(unique.values()))
        return None

    def section_at(self, path, line):
        matches = [s for s in self.sections.values() if s["path"] == path and s["heading"].start <= line < s["heading"].end]
        return min(matches, key=lambda s: s["heading"].end - s["heading"].start) if matches else None


def load_json(data, path, diagnostics):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                diagnostics.add("D02", f"malformed declaration: duplicate JSON key '{key}'", path)
            result[key] = value
        return result
    try:
        value = json.loads(data, object_pairs_hook=pairs)
        if not isinstance(value, dict):
            raise ValueError("expected an object")
        return value
    except (ValueError, UnicodeError) as exc:
        diagnostics.add("D02", f"malformed declaration: {exc}", path)
        return {}


def shape(value, required, optional, diagnostics, path, detail):
    if not isinstance(value, dict):
        diagnostics.add("D02", f"malformed declaration: {detail} must be an object", path)
        return False
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        diagnostics.add("D02", f"malformed declaration: {detail}; missing {sorted(missing)}, unknown {sorted(unknown)}", path)
        return False
    return True


def strings(value):
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


def read_text(source, path, diagnostics):
    if path in source.problems and source.problems[path] == "missing input":
        diagnostics.add("D27", f"cannot read '{path}': input is missing", path)
        return None
    if not safe_path(path) or path in source.problems:
        diagnostics.add("D05", f"source '{path}' is outside the declared input set: {source.problems.get(path, 'path escape')}", path)
        return None
    if path not in source.files:
        diagnostics.add("D27", f"cannot read '{path}': input is missing", path)
        return None
    try:
        return source.files[path].decode("utf-8")
    except UnicodeError as exc:
        diagnostics.add("D05", f"source '{path}' is outside the declared input set: invalid UTF-8 ({exc})", path)
        return None


def load_corpus(source, format_contract=None, *, comparison=False):
    """Load metadata, parse each authored source once, and assemble the registry."""
    validate_runtime()
    if MarkdownIt is None:
        fail("D27", "cannot load parser: repair the environment from the unchanged lock", "runtime", 2)
    if not isinstance(source, Snapshot):
        source = Snapshot.from_mapping(source)
    diagnostics = Diagnostics()
    contract_path = REFERENCE if format_contract is None else format_contract
    contract = load_json(Path(contract_path).read_bytes(), str(contract_path), diagnostics) if isinstance(contract_path, (str, Path)) else contract_path
    contract_fields = ["version", "entity_kinds", "inventory_kinds", "document_statuses", "roles", "design_roles", "relationship_targets", "requirement_fields", "test_fields", "failure_fields", "scenario_fields", "review_responsibilities", "group_separators"]
    if not shape(contract, contract_fields, [], diagnostics, "format-contract", "format contract"):
        raise SpecDocsError(diagnostics, 2)
    if type(contract["version"]) is not int or contract["version"] != 1:
        diagnostics.add("D02", "unsupported version: format contract", "format-contract")
    for name in set(contract_fields) - {"version", "relationship_targets", "group_separators"}:
        if not strings(contract[name]):
            diagnostics.add("D02", f"malformed declaration: format {name} must be text array", "format-contract")
    if not isinstance(contract["group_separators"], list) or not all(isinstance(value, str) and len(value) == 1 for value in contract["group_separators"]):
        diagnostics.add("D02", "malformed declaration: group separators must be single characters", "format-contract")
    relations = contract["relationship_targets"]
    if not isinstance(relations, dict) or not all(strings(kinds) for kinds in relations.values()):
        diagnostics.add("D02", "malformed declaration: relationship target kinds", "format-contract")
    if diagnostics.errors:
        raise SpecDocsError(diagnostics, 2)
    corpus = Corpus(source, contract, diagnostics)
    if comparison and not any(path in source.files or path in source.tracked for path in JSON_PATHS):
        # Before adoption, there are no declared requirements to compare. Partial
        # metadata still follows normal validation and fails visibly.
        return corpus
    if type(contract.get("version")) is not int or contract["version"] != 1:
        diagnostics.add("D02", "unsupported version: format contract")
    for path, attribute in zip(JSON_PATHS, ("index", "manifest")):
        text = read_text(source, path, diagnostics)
        setattr(corpus, attribute, load_json(text or "{}", path, diagnostics))
    ep, mp = JSON_PATHS
    if not shape(corpus.index, ["version", "entities", "naming_rules"], [], diagnostics, ep, "entity index"):
        corpus.index = {"entities": {}, "naming_rules": []}
    if not shape(corpus.manifest, ["version", "inventory", "documents"], [], diagnostics, mp, "document manifest"):
        corpus.manifest = {"inventory": [], "documents": []}
    for path, data in ((ep, corpus.index), (mp, corpus.manifest)):
        if type(data.get("version")) is not int or data["version"] != 1:
            diagnostics.add("D02", "unsupported version: expected 1", path)
    inventory = {}
    entries = corpus.manifest.get("inventory", [])
    if not isinstance(entries, list):
        diagnostics.add("D02", "malformed declaration: inventory must be an array", mp)
        entries = []
    for entry in entries:
        if not shape(entry, ["path", "kind"], ["reason"], diagnostics, mp, "inventory entry"):
            continue
        path, kind = entry["path"], entry["kind"]
        if not safe_path(path) or kind not in contract["inventory_kinds"]:
            diagnostics.add("D02", "malformed declaration: inventory path or kind", mp)
            continue
        if path in inventory:
            diagnostics.add("D03", f"duplicate identity '{path}'; first at {mp}")
        inventory[path] = kind
        if kind == "other" and not (isinstance(entry.get("reason"), str) and entry["reason"].strip()):
            diagnostics.add("D02", f"malformed declaration: other classification '{path}' needs a reason", mp)
        if kind != "generated":
            text = read_text(source, path, diagnostics)
            if text is not None and kind in ("specification", "design"):
                corpus.markdown[path] = parse_markdown(path, text, diagnostics)
    corpus.inventory = inventory
    navigation_paths = {d.get("navigation", {}).get("path") for d in corpus.manifest.get("documents", []) if isinstance(d, dict) and isinstance(d.get("navigation", {}), dict) and isinstance(d.get("navigation", {}).get("path"), str)} if isinstance(corpus.manifest.get("documents"), list) else set()
    for path in sorted(source.tracked):
        if path.lower().endswith(".md") and path not in inventory and path not in navigation_paths:
            diagnostics.add("D01", f"tracked Markdown file is not classified: {path}", path)
    docs = corpus.manifest.get("documents", [])
    if not isinstance(docs, list):
        diagnostics.add("D02", "malformed declaration: documents must be an array", mp)
        docs = []
    for document in docs:
        required = ["id", "title", "status", "purpose", "audience", "scope", "non_goals", "navigation", "sections", "scenarios"]
        if not shape(document, required, ["approval", "gaps", "unresolved_contracts"], diagnostics, mp, "document"):
            continue
        if not all(isinstance(document[k], str) and document[k].strip() for k in required[:7]):
            diagnostics.add("D02", "malformed declaration: document text fields", mp)
            continue
        identity = document["id"]
        if identity in corpus.documents:
            diagnostics.add("D03", f"duplicate identity '{identity}'; first at {mp}")
        if document["status"] not in contract["document_statuses"]:
            diagnostics.add("D02", "malformed declaration: document status", mp)
        nav = document["navigation"]
        if not shape(nav, ["path"], ["region"], diagnostics, mp, "navigation") or not safe_path(nav.get("path")):
            diagnostics.add("D05", f"source '{nav}' is outside the declared input set: navigation path", mp)
        elif nav.get("region"):
            if nav["region"] != identity or nav["path"] not in corpus.markdown:
                diagnostics.add("D02", "malformed declaration: navigation region must belong to this document", mp)
        elif not nav["path"].startswith("docs/generated/"):
            diagnostics.add("D05", f"source '{nav['path']}' is outside the declared input set: generated directory", mp)
        if not strings(document["scenarios"]) or not isinstance(document["sections"], list):
            diagnostics.add("D02", "malformed declaration: sections/scenarios", mp)
            continue
        corpus.documents[identity] = document
        for order, section in enumerate(document["sections"]):
            if not shape(section, ["id", "path", "anchor", "roles", "summary", "prerequisites", "explanatory_dependencies"], [], diagnostics, mp, "section"):
                continue
            if not all(isinstance(section[k], str) and section[k].strip() for k in ("id", "path", "anchor", "summary")) or not strings(section["roles"]) or not strings(section["prerequisites"]) or not isinstance(section["explanatory_dependencies"], list):
                diagnostics.add("D02", "malformed declaration: section fields", mp)
                continue
            key = identity + "#" + section["id"]
            if key in corpus.sections:
                diagnostics.add("D03", f"duplicate identity '{key}'; first at {mp}")
            markdown = corpus.markdown.get(section["path"])
            heading = next((h for h in markdown.headings if h.anchor == section["anchor"]), None) if markdown else None
            if not heading:
                diagnostics.add("D06", f"target '{key}' does not resolve", section["path"])
                continue
            corpus.sections[key] = dict(section, document=identity, order=order, heading=heading, selector=key)
            for dep in section["explanatory_dependencies"]:
                if not shape(dep, ["section", "reason"], [], diagnostics, mp, "dependency") or not all(isinstance(v, str) and v.strip() for v in dep.values()):
                    diagnostics.add("D02", "malformed declaration: dependency needs section and reason", mp)
            if set(section["roles"]) - set(contract["roles"] + contract["design_roles"]):
                diagnostics.add("D02", "malformed declaration: unknown section role", mp)
    raw_entities = corpus.index.get("entities", {})
    if not isinstance(raw_entities, dict):
        diagnostics.add("D02", "malformed declaration: entities must be an object", ep)
        raw_entities = {}
    for identity, entity in raw_entities.items():
        if not shape(entity, ["kind", "home", "scope", "forms", "symbols", "rejected_forms"], [], diagnostics, ep, "entity"):
            continue
        if not isinstance(entity["kind"], str) or entity["kind"] not in contract["entity_kinds"] or not all(strings(entity[k]) for k in ("scope", "forms", "symbols")) or not isinstance(entity["rejected_forms"], list):
            diagnostics.add("D02", f"malformed declaration: entity '{identity}'", ep)
            continue
        home = entity["home"]
        if not shape(home, ["section", "anchor"], [], diagnostics, ep, "home") or not all(isinstance(v, str) for v in home.values()):
            continue
        section = corpus.sections.get(home["section"])
        md = corpus.markdown.get(section["path"]) if section else None
        heading = next((h for h in md.headings if h.anchor == home["anchor"] and section["heading"].start <= h.start < section["heading"].end), None) if md else None
        meaning = ""
        if heading:
            paragraphs = [t for i, t in enumerate(md.tokens) if t.type == "inline" and t.map and not any(a <= t.map[0] < b for a, b in md.generated) and heading.start < t.map[0] < heading.intro_end and i > 0 and md.tokens[i - 1].type == "paragraph_open" and visible(t.children).strip()]
            meaning = visible(paragraphs[0].children).strip() if paragraphs else ""
        if not heading or not meaning or len(md.anchors.get(home["anchor"], [])) != 1:
            diagnostics.add("D04", f"entity '{identity}' has no complete, unique home", ep)
            continue
        if any(e["path"] == md.path and e["anchor"] == heading.anchor for e in corpus.entities.values()):
            diagnostics.add("D04", f"entity '{identity}' has no complete, unique home", md.path, heading.start + 1)
        for rejected in entity["rejected_forms"]:
            if shape(rejected, ["text", "replacement", "reason"], [], diagnostics, ep, "rejected form") and not all(isinstance(v, str) and v.strip() for v in rejected.values()):
                diagnostics.add("D02", "malformed declaration: rejected form fields must be nonempty text", ep)
        if set(entity["scope"]) - corpus.documents.keys() or section["document"] not in entity["scope"]:
            diagnostics.add("D07", f"entity '{identity}' is used outside its declared document scope", ep)
        corpus.entities[identity] = dict(entity, id=identity, path=md.path, anchor=heading.anchor,
                                        title=heading.title, meaning=meaning, start=heading.start - 1,
                                        end=heading.end, facts={})
    try:
        profile_text = PROFILE.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        diagnostics.add("D27", f"cannot read tool writing profile: {exc}", PROFILE_PATH)
        profile_text = None
    if profile_text is not None:
        # The shared owner marks one JSON profile; no second limits file exists.
        profile_blocks = []
        for token in MarkdownIt("commonmark").parse(profile_text):
            if token.type == "fence" and token.info.strip() in ("json", "json writing-profile"):
                try:
                    candidate = json.loads(token.content)
                except ValueError:
                    continue
                if isinstance(candidate, dict) and ("profile" in candidate or "descriptive_sentence_words" in candidate):
                    profile_blocks.append(candidate)
        if len(profile_blocks) != 1:
            diagnostics.add("D02", "malformed declaration: writing rules need one machine-readable writing profile", PROFILE_PATH)
        else:
            corpus.profile = profile_blocks[0]
            corpus.profile_bytes = canonical(corpus.profile)
            shape(corpus.profile, ["version", "name", "procedure_sentence_words", "descriptive_sentence_words", "descriptive_paragraph_sentences", "severity"], [], diagnostics, PROFILE_PATH, "writing profile")
            if not isinstance(corpus.profile.get("name"), str) or not corpus.profile["name"] or corpus.profile.get("severity") != "warning":
                diagnostics.add("D02", "malformed declaration: profile needs a name and warning severity", PROFILE_PATH)
            if type(corpus.profile.get("version")) is not int or corpus.profile["version"] != 1:
                diagnostics.add("D02", "unsupported version: writing profile", PROFILE_PATH)
    resolve_links(corpus)
    assemble_declarations(corpus)
    return corpus


def resolve_links(corpus):
    targets = dict(corpus.markdown)
    for md in corpus.markdown.values():
        for link in md.links:
            try:
                parsed = urlsplit(link.target)
                if parsed.scheme or parsed.netloc:
                    if parsed.scheme not in ("https", "http", "mailto") or (parsed.scheme in ("http", "https") and not parsed.hostname) or re.search(r"\s", link.target):
                        raise ValueError("invalid external URL")
                    continue
                path = posixpath.normpath(posixpath.join(posixpath.dirname(md.path), unquote(parsed.path))) if parsed.path else md.path
                anchor = unquote(parsed.fragment)
                if anchor and path.lower().endswith(".md") and path not in targets and path in corpus.inventory:
                    text = read_text(corpus.source, path, corpus.diagnostics)
                    if text is not None:
                        targets[path] = parse_markdown(path, text, corpus.diagnostics)
                if not safe_path(path) or path in corpus.source.problems:
                    corpus.diagnostics.add("D05", f"source '{path}' is outside the declared input set: link escape or nonregular input", md.path, link.line + 1)
                elif (path not in corpus.source.files and path not in corpus.source.tracked) or (anchor and path.lower().endswith(".md") and (path not in targets or len(targets[path].anchors.get(anchor, [])) != 1)):
                    raise ValueError("missing local target")
                else:
                    link.destination = path, anchor
            except ValueError:
                corpus.diagnostics.add("D06", f"target '{link.target}' does not resolve", md.path, link.line + 1)


def assemble_declarations(corpus):
    d = corpus.diagnostics
    trace_identities = {}
    for md in corpus.markdown.values():
        for heading in md.headings:
            prefix = next((name for name in ("Requirement", "Acceptance test", "Failure state", "Scenario") if heading.title.startswith(name + ":")), None)
            if not prefix and heading.anchor and heading.anchor.startswith("test-"):
                prefix = "Acceptance test"
            if not prefix:
                continue
            section = corpus.section_at(md.path, heading.start)
            if not heading.anchor or not section:
                d.add("D02", "malformed declaration: declaration needs a stable anchor and manifest section", md.path, heading.start + 1)
                continue
            if prefix in ("Requirement", "Acceptance test"):
                required_prefix = "req-" if prefix == "Requirement" else "test-"
                if not re.fullmatch(required_prefix + r"[a-z0-9]+(?:-[a-z0-9]+)*", heading.anchor):
                    d.add("D02", f"malformed declaration: {prefix} anchor must be {required_prefix}<kebab-case identity>", md.path, heading.start + 1)
                if heading.anchor in trace_identities:
                    d.add("D03", f"duplicate identity '{heading.anchor}'; first at {trace_identities[heading.anchor]}", md.path, heading.start + 1)
                else:
                    trace_identities[heading.anchor] = f"{md.path}:{heading.start + 1}"
            selector = section["document"] + "#" + heading.anchor
            if selector in corpus.declarations:
                d.add("D03", f"duplicate identity '{selector}'; first at {corpus.declarations[selector]['path']}", md.path, heading.start + 1)
            corpus.declarations[selector] = dict(id=selector, kind=prefix, path=md.path, heading=heading,
                                               fields=heading.fields, text=md.range_bytes(heading.start - 1, heading.end).decode())
        for cells, line, headers in md.rows:
            if headers not in (["Key", "Value", "Status", "Basis"], ["Key", "Predicate", "Target", "Basis"]):
                if headers and headers[0] == "Key" and ("Value" in headers or "Predicate" in headers):
                    d.add("D02", "malformed declaration: unknown fact or relation columns", md.path, line + 1)
                continue
            if len(cells) != 4:
                d.add("D02", "malformed declaration: table row needs four cells", md.path, line + 1)
                continue
            owners = [e for e in corpus.entities.values() if e["path"] == md.path and e["start"] < line < e["end"]]
            owner = min(owners, key=lambda e: e["end"] - e["start"]) if owners else None
            if not owner:
                d.add("D04", "entity '<table owner>' has no complete, unique home", md.path, line + 1)
                continue
            values = [visible(t.children).strip() for t in cells]
            if headers[1] == "Value":
                key, value, status, basis = values
                identity = owner["id"] + "#" + key
                ids = [a for t in cells[0].children or [] if t.type == "html_inline" for a in anchors(t.content)[0]]
                all_ids = [a for cell in cells for t in cell.children or [] if t.type == "html_inline" for a in anchors(t.content)[0]]
                if len(ids) != 1 or len(all_ids) != 1 or len(md.anchors.get(ids[0], [])) != 1:
                    d.add("D08", f"fact '{identity}' needs exactly one home anchor in its declaring row", md.path, line + 1)
                    continue
                if identity in corpus.facts:
                    d.add("D03", f"duplicate identity '{identity}'; first at {corpus.facts[identity]['path']}", md.path, line + 1)
                if not key or not value or not status or not basis or not md.inline_links.get(id(cells[3])):
                    d.add("D02", f"malformed declaration: fact '{identity}' needs Key, Value, Status and linked Basis", md.path, line + 1)
                qualifications = []
                for token in md.tokens:
                    if token.type == "inline" and token.map and owner["start"] < token.map[0] < owner["end"] and not (line <= token.map[0] <= line):
                        if any(link.destination == (md.path, ids[0]) for link in md.inline_links.get(id(token), [])):
                            qualifications.append(token.content)
                fact = dict(id=identity, owner=owner["id"], key=key, value=value, status=status, basis=basis,
                            basis_targets=[l.target for l in md.inline_links.get(id(cells[3]), [])],
                            qualifications=qualifications, path=md.path, anchor=ids[0], line=line)
                corpus.facts[identity] = fact
                owner["facts"][key] = fact
            else:
                predicate = values[1]
                targets = md.inline_links.get(id(cells[2]), [])
                bases = md.inline_links.get(id(cells[3]), [])
                if predicate not in corpus.contract["relationship_targets"] or len(targets) != 1 or not bases:
                    d.add("D02", "malformed declaration: relation predicate, target or Basis", md.path, line + 1)
                    continue
                target = next((e for e in corpus.entities.values() if (e["path"], e["anchor"]) == targets[0].destination), None)
                if not target or target["kind"] not in corpus.contract["relationship_targets"][predicate]:
                    d.add("D02", "malformed declaration: unsupported relationship target kind", md.path, line + 1)


def normalize_literal(text, contract):
    """Normalize grouping only, never evaluate measurements or value expressions."""
    separators = "".join(contract["group_separators"])
    group = "[" + re.escape(separators) + "]"
    # A grouped integer may precede a decimal part; the dot remains unchanged.
    pattern = r"(?<![\w.,])\d{1,3}(?:" + group + r"\d{3})+(?!\d|,\d)"
    return re.sub(pattern, lambda m: re.sub(group, "", m[0]), text.strip())


def declaration_targets(corpus, declaration, field_name):
    destinations = {link.destination for link in declaration["fields"].get(field_name, ("", []))[1]}
    return {key for key, item in corpus.declarations.items()
            if (item["path"], item["heading"].anchor) in destinations}


def check_implementation(corpus, declaration, diagnostics):
    """Validate test-file links while leaving selector existence to the later pass."""
    md = corpus.markdown[declaration["path"]]
    heading = declaration["heading"]
    token = next(t for t in md.tokens if t.type == "inline" and t.map
                 and heading.start < t.map[0] < heading.intro_end
                 and re.match(r"^\*\*Implementation:\*\*", t.content))
    children = token.children
    start = next(i for i, child in enumerate(children) if child.type == "strong_close") + 1
    tail = children[start:]
    while tail and tail[0].type in ("text", "softbreak") and not tail[0].content.strip():
        tail = tail[1:]
    valid, count, i = True, 0, 0
    while i < len(tail):
        group = tail[i:i + 3]
        if [t.type for t in group] != ["link_open", "text", "link_close"]:
            valid = False
            break
        file, separator, selector = group[1].content.partition("::")
        try:
            target = urlsplit(group[0].attrGet("href") or "")
        except ValueError:
            valid = False
            break
        path = posixpath.normpath(posixpath.join(posixpath.dirname(md.path), unquote(target.path)))
        if (not separator or not selector or re.search(r"\s", selector)
                or not target.path or target.scheme or target.netloc or target.query or target.fragment
                or not safe_path(path) or file != path):
            valid = False
        count += 1
        i += 3
        gap = ""
        while i < len(tail) and tail[i].type in ("text", "softbreak", "hardbreak"):
            gap += tail[i].content if tail[i].type == "text" else "\n"
            i += 1
        if (i < len(tail) and not re.fullmatch(r",\s+", gap)) or (i == len(tail) and gap.strip()):
            valid = False
    if not valid or not count:
        diagnostics.add("D02", f"malformed declaration: '{declaration['id']}' Implementation requires comma-separated [repository-file::selector](relative-file) links", md.path, token.map[0] + 1)


def check(corpus, base=None, _freshness=True):
    """Check declarations and projections; return every available diagnostic."""
    d = Diagnostics(corpus.diagnostics.items[:])
    ep, mp = JSON_PATHS
    for section in corpus.sections.values():
        for dep in section["explanatory_dependencies"]:
            if isinstance(dep, dict) and isinstance(dep.get("section"), str) and dep["section"] not in corpus.sections:
                d.add("D06", f"target '{dep['section']}' does not resolve")
        md = corpus.markdown[section["path"]]
        for prerequisite in section["prerequisites"]:
            target = corpus.sections.get(prerequisite)
            if not target:
                d.add("D06", f"target '{prerequisite}' does not resolve")
            elif target["document"] != section["document"] or target["order"] > section["order"]:
                if not any(link.destination == (target["path"], target["anchor"]) and section["heading"].start <= link.line < section["heading"].end for link in md.links):
                    d.add("D16", f"prerequisite '{prerequisite}' appears later without a direct forward link", section["path"], section["heading"].start + 1)
    for document in corpus.documents.values():
        sections = [s for s in corpus.sections.values() if s["document"] == document["id"]]
        roles = {role for s in sections if corpus.markdown[s["path"]].range_bytes(s["heading"].start + 1, s["heading"].end).strip() for role in s["roles"]}
        required = corpus.contract["roles"][:]
        if any(kind == "design" and path in {s["path"] for s in sections} for path, kind in corpus.inventory.items()):
            required += corpus.contract["design_roles"]
        gaps = document.get("gaps", [])
        if not strings(gaps):
            d.add("D02", "malformed declaration: gaps must be role names")
            gaps = []
        for role in required:
            if role not in roles and not (document["status"] == "draft" and role in gaps):
                d.add("D15", f"required document role '{role}' is missing or incomplete")
        tour_orders = [section["order"] for section in sections if "tour" in section["roles"]]
        mechanism_orders = [section["order"] for section in sections if "mechanism" in section["roles"]]
        reference_orders = [section["order"] for section in sections if "reference" in section["roles"]]
        if tour_orders and mechanism_orders and min(tour_orders) > min(mechanism_orders):
            d.add("D15", "required document role 'tour' is missing or incomplete: place the tour before mechanisms")
        if mechanism_orders and reference_orders and min(reference_orders) < max(mechanism_orders):
            d.add("D15", "required document role 'reference' is missing or incomplete: place reference after mechanisms")
        for selector in document["scenarios"]:
            if selector not in corpus.declarations or corpus.declarations[selector]["kind"] != "Scenario":
                d.add("D06", f"target '{selector}' does not resolve")
        approval = document.get("approval")
        if document["status"] == "approved" or approval is not None:
            if not shape(approval, ["authority", "decision"], [], d, mp, "approval"):
                continue
            authorities = ("operator", "delegated", "fixture") if corpus.source.fixture else ("operator", "delegated")
            if approval.get("authority") not in authorities:
                d.add("D02", "malformed declaration: approval authority")
            if not corpus.locate(approval.get("decision")):
                d.add("D06", f"target '{approval.get('decision')}' does not resolve")
            if document["status"] == "approved" and isinstance(document.get("unresolved_contracts", []), list):
                for contract in document.get("unresolved_contracts", []):
                    d.add("D21", f"approval is blocked by unresolved contract '{contract}'")
        if not strings(document.get("unresolved_contracts", [])):
            d.add("D02", "malformed declaration: unresolved_contracts must be selectors")
        else:
            for selector in document.get("unresolved_contracts", []):
                if not corpus.locate(selector):
                    d.add("D06", f"target '{selector}' does not resolve")
    rules = corpus.index.get("naming_rules", [])
    if not isinstance(rules, list):
        d.add("D02", "malformed declaration: naming rules must be an array", ep)
        rules = []
    identities, symbols = set(), {}
    for rule in rules:
        if not shape(rule, ["id", "kind", "field", "pattern", "message"], [], d, ep, "naming rule"):
            continue
        if not all(isinstance(rule[k], str) and rule[k] for k in rule):
            d.add("D02", "malformed declaration: naming rule fields must be nonempty text", ep)
            continue
        if rule["id"] in identities:
            d.add("D03", f"duplicate identity '{rule['id']}'; first at {ep}", ep)
        identities.add(rule["id"])
        try:
            if rule["field"] not in ("forms", "symbols") or rule["kind"] not in corpus.contract["entity_kinds"]:
                raise ValueError("unsupported field or kind")
            pattern = re.compile(rule["pattern"])
        except (ValueError, TypeError, re.error) as exc:
            d.add("D02", f"malformed naming pattern: {exc}", ep)
            continue
        for entity in corpus.entities.values():
            if entity["kind"] == rule["kind"]:
                for value in entity[rule["field"]]:
                    if not pattern.fullmatch(value):
                        d.add("D14", f"symbol '{value}' violates naming rule '{rule['id']}'", ep)
    for entity in corpus.entities.values():
        for symbol in entity["symbols"]:
            if symbol in symbols:
                d.add("D03", f"duplicate identity '{symbol}'; first at {symbols[symbol]}", ep)
            symbols[symbol] = entity["id"]
    for md in corpus.markdown.values():
        for link in md.links:
            section = corpus.section_at(md.path, link.line)
            for entity in corpus.entities.values():
                if section and link.destination in use_targets(corpus, entity) and section["document"] not in entity["scope"]:
                    d.add("D07", f"entity '{entity["id"]}' is used outside its declared document scope", md.path, link.line + 1)
            fact = next((f for f in corpus.facts.values() if (f["path"], f["anchor"]) == link.destination), None)
            if fact:
                owner = corpus.entities[fact["owner"]]
                descriptive = [fact["key"], owner["title"], *owner["forms"], *owner["symbols"]]
                if link.label.casefold() not in {x.casefold() for x in descriptive} and normalize_literal(link.label, corpus.contract) != normalize_literal(fact["value"], corpus.contract):
                    d.add("D10", f"value link for '{fact['id']}' differs: home {fact['value']!r}, link {link.label!r}", md.path, link.line + 1)
        check_uses(corpus, md, d)
        check_prose(corpus, md, d)
    for identity, declaration in corpus.declarations.items():
        kind, fields = declaration["kind"], declaration["fields"]
        required = corpus.contract[{"Requirement": "requirement_fields", "Acceptance test": "test_fields", "Failure state": "failure_fields", "Scenario": "scenario_fields"}[kind]]
        optional = {"Entities in this example"}
        if kind == "Acceptance test":
            optional.add("Implementation")
        elif kind == "Failure state":
            optional.add("Actor")
        elif kind == "Scenario":
            optional.update(("Requirements", "Tests"))
        for unknown in sorted(fields.keys() - set(required) - optional):
            d.add("D02", f"malformed declaration: '{identity}' has unknown field '{unknown}'", declaration["path"], declaration["heading"].start + 1)
        for name in required:
            if not fields.get(name, ("", []))[0].strip():
                code = "D30" if kind == "Failure state" else "D02"
                message = f"failure declaration '{identity}' lacks '{name}'" if code == "D30" else f"malformed declaration: '{identity}' lacks '{name}'"
                d.add(code, message, declaration["path"], declaration["heading"].start + 1)
        if kind == "Requirement":
            tests = declaration_targets(corpus, declaration, "Tests")
            tests = {key for key in tests if corpus.declarations[key]["kind"] == "Acceptance test"}
            if not tests:
                d.add("D11", f"requirement '{identity}' has no linked acceptance test", declaration["path"], declaration["heading"].start + 1)
            for test in tests:
                if identity not in declaration_targets(corpus, corpus.declarations[test], "Requirements"):
                    d.add("D29", f"requirement/test link '{identity}' <-> '{test}' is not reciprocal", declaration["path"], declaration["heading"].start + 1)
        if kind == "Acceptance test":
            if "Implementation" in fields:
                check_implementation(corpus, declaration, d)
            requirements = declaration_targets(corpus, declaration, "Requirements")
            requirements = {key for key in requirements if corpus.declarations[key]["kind"] == "Requirement"}
            if not requirements:
                d.add("D28", f"acceptance test '{identity}' has no linked requirement", declaration["path"], declaration["heading"].start + 1)
            for req in requirements:
                if identity not in declaration_targets(corpus, corpus.declarations[req], "Tests"):
                    d.add("D29", f"requirement/test link '{req}' <-> '{identity}' is not reciprocal", declaration["path"], declaration["heading"].start + 1)
    if base is not None:
        report = requirement_changes(base, corpus)
        assignment = corpus.assignment or {}
        removals = assignment.get("removal_decisions", {})
        reviews = assignment.get("required_test_reviews", [])
        for change in report.changes:
            identity = change["id"]
            if change["kind"] == "removed" and not corpus.locate(removals.get(identity)):
                d.add("D22", f"removed requirement '{identity}' needs a resolving decision reference")
            for test in change["tests"]:
                if test not in reviews:
                    d.add("D31", f"changed requirement '{identity}' lacks linked-test review input '{test}'")
    # Freshness is computed only after structural validation; invalid sources cannot generate.
    if _freshness and not d.errors:
        try:
            for path, expected in project_navigation(corpus).items():
                if corpus.source.files.get(path) != expected:
                    d.add("D17", f"generated navigation differs: regenerate '{path}'", path)
        except SpecDocsError as exc:
            d.items.extend(exc.diagnostics.items)
    return d


def phrase_pattern(text, exact=False):
    return re.compile(r"(?<!\w)" + re.escape(text) + r"(?!\w)", 0 if exact else re.I)


def recognized(corpus, text):
    """Return longest registered phrase matches; ambiguity is retained for review."""
    matches = []
    for identity, entity in corpus.entities.items():
        for phrase in set([entity["title"], *entity["forms"]]):
            matches.extend((m.start(), m.end(), identity, phrase, False) for m in phrase_pattern(phrase).finditer(text))
        for symbol in entity["symbols"]:
            matches.extend((m.start(), m.end(), identity, symbol, True) for m in phrase_pattern(symbol, True).finditer(text))
    matches.sort(key=lambda m: (m[0], -(m[1] - m[0]), m[2]))
    occupied, output = [], []
    for match in matches:
        if not any(a <= match[0] and match[1] <= b and (a, b) != match[:2] for a, b in occupied):
            output.append(match)
            occupied.append(match[:2])
    return output


def use_targets(corpus, entity):
    return {(entity["path"], entity["anchor"])} | {(f["path"], f["anchor"]) for f in entity["facts"].values()}


def inline_spans(token, links):
    text, link_spans, code_spans = "", [], []
    active, index = None, 0
    for child in token.children or []:
        if child.type == "link_open":
            active = (len(text), links[index]) if index < len(links) else None
            index += 1
        elif child.type == "link_close" and active is not None:
            link_spans.append((active[0], len(text), active[1]))
            active = None
        elif child.type in ("text", "code_inline"):
            if child.type == "code_inline":
                code_spans.append((len(text), len(text) + len(child.content)))
            text += child.content
        elif child.type in ("softbreak", "hardbreak"):
            text += "\n"
    return text, link_spans, code_spans


def check_uses(corpus, md, diagnostics):
    seen = set()
    for token_index, token in enumerate(md.tokens):
        if not token.map or any(a <= token.map[0] < b for a, b in md.generated):
            continue
        line = token.map[0]
        if token.type not in ("inline", "fence", "code_block"):
            continue
        if token.type == "inline" and not visible(token.children).strip():
            continue
        is_heading = token.type == "inline" and token_index and md.tokens[token_index - 1].type == "heading_open"
        if is_heading:
            if md.inline_links.get(id(token)):
                diagnostics.add("D33", "heading contains a link: move it into the section text", md.path, line + 1)
            if re.match(r"^(?:§|\d+\.(?:\d+(?:\.\d+)*\.?)?(?=\s|$))", visible(token.children)):
                diagnostics.add("D32", "heading starts with a section number: use an unnumbered name", md.path, line + 1)
        section = corpus.section_at(md.path, line)
        if not section:
            diagnostics.add("D05", f"source '{md.path}' is outside the declared input set: content is not assigned to a manifest section", md.path, line + 1)
            continue
        heading = md.intro_at(line)
        use_section = md.use_section_at(line)
        local = use_section.start if use_section else -1
        # Defining heading and first nonempty paragraph may omit their own link.
        intro = next((t for i, t in enumerate(md.tokens) if t.type == "inline" and t.map and heading and heading.start < t.map[0] < heading.intro_end and i and md.tokens[i - 1].type == "paragraph_open" and visible(t.children).strip()), None)
        literal = token.type in ("fence", "code_block")
        links = md.inline_links.get(id(token), [])
        if literal:
            text, link_spans, code_spans = token.content, [], []
        else:
            text, link_spans, code_spans = inline_spans(token, links)
        hits = recognized(corpus, text)
        grouped = defaultdict(list)
        for hit in hits:
            grouped[hit[:2]].append(hit)
        for span, group in grouped.items():
            entity_ids = {h[2] for h in group}
            if len(entity_ids) > 1:
                diagnostics.add("W04", f"Possible technical use needs review: '{text[span[0]:span[1]]}'", md.path, line + 1)
                continue
            identity = next(iter(entity_ids))
            entity = corpus.entities[identity]
            if section["document"] not in entity["scope"]:
                diagnostics.add("D07", f"entity '{identity}' is used outside its declared document scope", md.path, line + 1)
            if is_heading:
                continue  # Headings name concepts but do not satisfy body first uses.
            if heading and heading.anchor == entity["anchor"] and md.path == entity["path"] and (line == heading.start or token is intro):
                seen.add((local, identity))
                continue
            entity_section = corpus.sections.get(entity["home"]["section"])
            forward = entity_section is None or entity_section["document"] != section["document"] or (entity_section["order"], entity["start"]) > (section["order"], line)
            links = md.inline_links.get(id(token), [])
            matched_link = False
            wrong_link = False
            for begin, end, link in link_spans:
                if begin <= span[0] and span[1] <= end:
                    if link.destination in use_targets(corpus, entity):
                        matched_link = True
                    else:
                        wrong_link = True
            # A literal requires its own neighboring annotation, even on a later use.
            code_use = any(begin <= span[0] and span[1] <= end for begin, end in code_spans)
            if literal or code_use:
                neighbors = [t for t in md.tokens if t.type == "inline" and t.map and t.content.startswith("**Entities in this example:**") and (t.map[1] <= line and not any(x.strip() for x in md.text.splitlines()[t.map[1]:line]) or token.map[1] <= t.map[0] and not any(x.strip() for x in md.text.splitlines()[token.map[1]:t.map[0]]))]
                matched_link |= any(link.destination in use_targets(corpus, entity) for n in neighbors for link in md.inline_links.get(id(n), []))
            needs_link = forward or (local, identity) not in seen or literal or code_use
            if wrong_link or (needs_link and not matched_link):
                reason = "wrong-target" if wrong_link else "forward-use" if forward and (local, identity) in seen else "first-use"
                diagnostics.add("D12", f"use of '{identity}' needs a direct home link: {reason}", md.path, line + 1)
            seen.add((local, identity))
        if not literal:
            for entity in corpus.entities.values():
                for rejected in entity["rejected_forms"]:
                    if isinstance(rejected, dict) and isinstance(rejected.get("text"), str) and phrase_pattern(rejected["text"]).search(text):
                        diagnostics.add("D13", f"rejected form '{rejected['text']}'; use '{rejected.get('replacement', '')}'", md.path, line + 1)


def sentences(children):
    # Protect code punctuation without changing its word count.
    text = "".join(re.sub(r"[.?!]", "·", t.content) if t.type == "code_inline" else
                   t.content if t.type == "text" else " " if t.type in ("softbreak", "hardbreak") else ""
                   for t in children or [])
    return [s.strip() for s in re.split(r"[.?!](?=\s|$)|:(?=\s*$)", text) if s.strip()]


def check_prose(corpus, md, diagnostics):
    profile = corpus.profile
    if not profile:
        return
    descriptive = profile.get("descriptive_sentence_words")
    procedure_words = profile.get("procedure_sentence_words")
    paragraph_sentences = profile.get("descriptive_paragraph_sentences")
    if not all(type(x) is int and x > 0 for x in (descriptive, procedure_words, paragraph_sentences)):
        diagnostics.add("D02", "malformed declaration: missing positive writing-profile targets", PROFILE_PATH)
        return
    declaration_cells = {id(cell) for cells, _line, headers in md.rows if headers in (["Key", "Value", "Status", "Basis"], ["Key", "Predicate", "Target", "Basis"]) for cell in cells}
    excluded_quotes, ordered_depth, cell_depth = [], 0, 0
    for i, token in enumerate(md.tokens):
        if token.type == "blockquote_open":
            nesting, quote_parts = 1, []
            for following in md.tokens[i + 1:]:
                if following.type == "blockquote_open":
                    nesting += 1
                elif following.type == "blockquote_close":
                    nesting -= 1
                    if not nesting:
                        break
                if following.type == "inline":
                    quote_parts.append(visible(following.children))
            attributed = any(re.match(r"^(?:—|--|–)\s+\S|^(?:Source|Attribution):", text) for text in quote_parts)
            excluded_quotes.append(attributed or any(excluded_quotes))
        elif token.type == "blockquote_close":
            excluded_quotes.pop()
        elif token.type in ("th_open", "td_open"):
            cell_depth += 1
        elif token.type in ("th_close", "td_close"):
            cell_depth -= 1
        elif token.type == "ordered_list_open":
            if ordered_depth == 0:
                depth, count = 1, 0
                for other in md.tokens[i + 1:]:
                    if other.type == "ordered_list_open":
                        depth += 1
                    elif other.type == "ordered_list_close":
                        depth -= 1
                        if not depth:
                            break
                    elif other.type == "list_item_open" and other.level == token.level + 1:
                        count += 1
                before = md.text.splitlines()[:token.map[0]]
                preceding = next((line.strip() for line in reversed(before) if line.strip()), "")
                rest = "\n".join(md.text.splitlines()[token.map[1]:])
                question = md.intro_at(token.map[0])
                exempt = bool(question and re.match(r"\d+\\?\.\s", question.title) and "**Answer like so:**" in rest)
                if not exempt and (not re.fullmatch(r"\*\*Procedure:\s+.+\*\*", preceding) or count < 2):
                    diagnostics.add("D18", "numbered list requires a labelled procedure with at least two actions", md.path, token.map[0] + 1)
            ordered_depth += 1
        elif token.type == "ordered_list_close":
            ordered_depth -= 1
        if id(token) in declaration_cells:
            continue
        if token.type != "inline" or not token.map or any(excluded_quotes) or any(a <= token.map[0] < b for a, b in md.generated):
            continue
        if token.content.startswith("**") and re.match(r"^\*\*[^*]+:\*\*", token.content):
            continue
        if i and md.tokens[i - 1].type == "heading_open":
            continue
        numeric_prose, link_spans, code_spans = inline_spans(token, md.inline_links.get(id(token), []))
        ignored_spans = [(a, b) for a, b, _ in link_spans] + code_spans
        numeric_prose = "".join(" " if any(a <= index < b for a, b in ignored_spans) else char for index, char in enumerate(numeric_prose))
        parts = sentences(token.children)
        limit = procedure_words if ordered_depth else descriptive
        for sentence in parts:
            words = len(sentence.split())
            if words > limit:
                diagnostics.add("W01", f"Sentence exceeds profile target: sentence has {words} words; profile target is {limit}", md.path, token.map[0] + 1)
            if (ordered_depth and (re.search(r"\b(?:is|are|be)\s+\w+ed\b", sentence) or re.search(r"\b(?:and then|then)\b", sentence))) or re.search(r"\b\d{1,3},\d{3}\b|\b\d+(?:ms|MiB|s|min)\b", numeric_prose):
                diagnostics.add("W05", "Passage may violate writing profile: voice, multiple actions or number format", md.path, token.map[0] + 1)
        if len(parts) > paragraph_sentences and not cell_depth:
            diagnostics.add("W02", f"Paragraph exceeds profile target: {len(parts)} sentences", md.path, token.map[0] + 1)
        if cell_depth and len(visible(token.children).split()) > descriptive:
            diagnostics.add("W05", "Passage may violate writing profile: long table cell", md.path, token.map[0] + 1)


def relative_link(output, path, anchor=""):
    relative = posixpath.relpath(path, posixpath.dirname(output) or ".")
    return relative + ("#" + anchor if anchor else "")


def replace_region(text, start, end, body, path):
    if text.count(start) != 1 or text.count(end) != 1 or text.index(start) >= text.index(end):
        fail("D02", "malformed declaration: expected exactly one ordered marker pair", path)
    first = text.index(start) + len(start)
    last = text.index(end)
    return (text[:first] + "\n" + body.rstrip() + "\n" + text[last:]).encode()


def generate_navigation(corpus):
    """Project authored navigation; return proposed bytes without writing files."""
    diagnostics = check(corpus, _freshness=False)
    if diagnostics.errors:
        raise SpecDocsError(diagnostics)
    return project_navigation(corpus)


def project_navigation(corpus):
    """Project an already validated corpus without another validation traversal."""
    outputs, wholly_generated = {}, []
    for document in corpus.documents.values():
        nav = document["navigation"]
        path = nav["path"]
        if path in outputs and not nav.get("region"):
            fail("D02", "malformed declaration: two documents own one generated file", path)
        sections = sorted((s for s in corpus.sections.values() if s["document"] == document["id"]), key=lambda s: s["order"])
        lines = ([] if nav.get("region") else [f"# {document['title']}", ""]) + ["<!-- Generated by spec-docs; edit authored declarations. -->", "",
                 "## Overview", "", document["purpose"], "", f"**Audience:** {document['audience']}", "",
                 f"**Scope:** {document['scope']}", "", f"**Non-goals:** {document['non_goals']}", ""]
        if document.get("gaps"):
            lines.extend(["**Declared gaps:** " + ", ".join(document["gaps"]), ""])
        lines.extend(["## Document map", ""])
        for section in sections:
            target = relative_link(path, section["path"], section["anchor"])
            lines.extend([f"- [{section['heading'].title}]({target}) — {section['summary']}"])
            md = corpus.markdown[section["path"]]
            for heading in md.headings:
                if (heading.level == 2 and heading.anchor != section["anchor"]
                        and section["heading"].start <= heading.start < section["heading"].end
                        and not any(a <= heading.start < b for a, b in md.generated)):
                    if not heading.anchor:
                        fail("D02", "malformed declaration: mapped level-2 heading needs an explicit anchor", md.path)
                    lines.append(f"  - [{heading.title}]({relative_link(path, md.path, heading.anchor)})")
            if section["prerequisites"]:
                prereqs = [corpus.sections[key] for key in section["prerequisites"]]
                lines.append("  Prerequisites: " + ", ".join(f"[{s['heading'].title}]({relative_link(path, s['path'], s['anchor'])})" for s in prereqs) + ".")
        lines.extend(["", "## Entity index", ""])
        for identity, entity in sorted(corpus.entities.items()):
            if document["id"] in entity["scope"]:
                lines.extend([f"- [{entity['title']}]({relative_link(path, entity['path'], entity['anchor'])}) (`{identity}`) — {entity['meaning']}"])
        body = "\n".join(lines) + "\n"
        if nav.get("region"):
            current = outputs.get(path, corpus.source.files.get(path, b"")).decode()
            start = START.format(document=nav["region"])
            rendered = replace_region(current, start, END, body, path).decode()
            # Place the region from the parsed source, immediately after the entry
            # title's opening paragraph. Generated headings never select that paragraph.
            md = corpus.markdown[path]
            title = next((h for h in md.headings if h.level == 1 and
                          not any(a <= h.start < b for a, b in md.generated)), None)
            opening = next((token for token in md.tokens if token.type == "paragraph_open"
                            and token.map and title and title.start < token.map[0] < title.intro_end
                            and not any(a <= token.map[0] < b for a, b in md.generated)), None)
            if opening is None:
                fail("D02", "malformed declaration: navigation entry needs a title and opening paragraph", path)
            insertion = sum(len(line) for line in md.text.splitlines(keepends=True)[:opening.map[1]])
            first, last = current.index(start), current.index(END) + len(END)
            region = rendered[rendered.index(start):rendered.index(END) + len(END)]
            outside = current[:first] + current[last:]
            if last <= insertion:
                insertion -= last - first
            elif first < insertion:
                fail("D02", "malformed declaration: navigation overlaps opening paragraph", path)
            text = outside[:insertion].rstrip("\n") + "\n\n" + region + "\n\n" + outside[insertion:].lstrip("\n")
            outputs[path] = (text.rstrip("\n") + "\n").encode()
        else:
            outputs[path] = body.encode()
            wholly_generated.append(path)
    if wholly_generated or ATTR_START.encode() in corpus.source.files.get(".gitattributes", b""):
        path = ".gitattributes"
        current = corpus.source.files.get(path, b"").decode()
        body = "\n".join(f'"{p}" linguist-generated=true' for p in sorted(wholly_generated))
        if ATTR_START in current or ATTR_END in current:
            outputs[path] = replace_region(current, ATTR_START, ATTR_END, body, path)
        else:
            outputs[path] = (current + ("\n" if current and not current.endswith("\n") else "") + ATTR_START + "\n" + body + "\n" + ATTR_END + "\n").encode()
    return outputs


@dataclass
class ChangeReport:
    """Derived requirement declarations, test links and directly changed facts."""
    changes: list[dict]

    def to_dict(self):
        return {"changes": self.changes}


def requirement_changes(base, candidate):
    """Select tests from both snapshots when a requirement or linked fact changes."""
    changes = []
    requirements = [{v["heading"].anchor: v for v in c.declarations.values()
                     if v["kind"] == "Requirement"} for c in (base, candidate)]
    for anchor in sorted(requirements[0].keys() | requirements[1].keys()):
        old, new = (items.get(anchor) for items in requirements)
        identity = (new or old)["id"]
        old_tests = declaration_targets(base, old, "Tests") if old else set()
        new_tests = declaration_targets(candidate, new, "Tests") if new else set()
        old_test_ids = {base.declarations[key]["heading"].anchor: key for key in old_tests}
        new_test_ids = {candidate.declarations[key]["heading"].anchor: key for key in new_tests}
        facts = set()
        for corpus, declaration in ((base, old), (candidate, new)):
            if declaration:
                destinations = {l.destination for value, links in declaration["fields"].values() for l in links}
                facts |= {key for key, fact in corpus.facts.items() if (fact["path"], fact["anchor"]) in destinations}
        changed_facts = []
        for key in sorted(facts):
            def contract(c):
                fact = c.facts.get(key)
                return {k: fact[k] for k in ("value", "status", "basis", "basis_targets", "qualifications")} if fact else None
            if contract(base) != contract(candidate):
                changed_facts.append({"id": key, "base": contract(base), "candidate": contract(candidate)})
        if not old or not new or old["text"] != new["text"] or changed_facts:
            changes.append(dict(id=identity, kind="new" if not old else "removed" if not new else "changed",
                                base=old["text"] if old else None, candidate=new["text"] if new else None,
                                tests=sorted(old_tests | new_tests),
                                added_tests=sorted(new_test_ids[key] for key in new_test_ids.keys() - old_test_ids.keys()),
                                removed_tests=sorted(old_test_ids[key] for key in old_test_ids.keys() - new_test_ids.keys()), changed_facts=changed_facts))
    return ChangeReport(changes)


@dataclass
class Context:
    """Complete mandatory context, with exact size and fingerprints."""
    content: bytes
    size_bytes: int
    manifest: dict
    diagnostics: Diagnostics

    def to_dict(self):
        return {"content": self.content.decode(), "size_bytes": self.size_bytes, "manifest": self.manifest}


def select_context(corpus, assignment):
    """Select the entire registry and deduplicated required ranges; never truncate."""
    d = Diagnostics()
    if not shape(assignment, ["version", "sections"], ["scenarios", "decisions", "baseline", "budget_bytes", "review_plan", "required_test_reviews", "removal_decisions", "label"], d, "assignment", "assignment"):
        raise SpecDocsError(d)
    if type(assignment["version"]) is not int or assignment["version"] != 1 or not strings(assignment["sections"]) or not assignment["sections"]:
        fail("D02", "malformed declaration: assignment needs version 1 and nonempty explicit sections", "assignment")
    for key in ("scenarios", "decisions", "required_test_reviews"):
        if not strings(assignment.get(key, [])):
            fail("D02", f"malformed declaration: assignment {key} must be selectors", "assignment")
    removals = assignment.get("removal_decisions", {})
    if not isinstance(removals, dict) or not all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in removals.items()):
        d.add("D02", "malformed declaration: removal_decisions must map requirements to decision selectors", "assignment")
    label = assignment.get("label", "candidate")
    if label not in ("base", "candidate") or (corpus.base is not None and label != "candidate"):
        d.add("D02", "malformed declaration: context with a comparison baseline must have candidate label", "assignment")
    if d.errors:
        raise SpecDocsError(d)
    corpus.assignment = assignment
    if corpus.base is not None:
        d.items.extend(check(corpus.base).items)
    d.items.extend(check(corpus, corpus.base).items)
    if d.errors:
        raise SpecDocsError(d)
    primary_label = assignment.get("label", "candidate")
    source_corpora = {primary_label: corpus}
    if corpus.base is not None:
        source_corpora["base"] = corpus.base
    baseline = corpus.source.revision or corpus.source.digest
    if assignment.get("baseline", baseline) != baseline:
        d.add("D24", "pack baseline differs from assignment baseline", "assignment")
    if assignment.get("label", "candidate") not in ("base", "candidate"):
        d.add("D02", "malformed declaration: context label", "assignment")
    if "review_plan" in assignment:
        plan = assignment["review_plan"]
        covered = set()
        if not isinstance(plan, list):
            d.add("D02", "malformed declaration: review_plan must be an array", "assignment")
        else:
            for reviewer in plan:
                if shape(reviewer, ["responsibilities"], ["id"], d, "assignment", "review entry"):
                    if not strings(reviewer["responsibilities"]) or set(reviewer["responsibilities"]) - set(corpus.contract["review_responsibilities"]):
                        d.add("D02", "malformed declaration: review responsibilities", "assignment")
                    else:
                        covered.update(reviewer["responsibilities"])
        for responsibility in corpus.contract["review_responsibilities"]:
            if responsibility not in covered:
                d.add("D26", f"review plan lacks required coverage '{responsibility}'", "assignment")
    selected, ranges, included = set(), [], {}
    pending = []

    def add_range(path, heading, identity, reason, label=None):
        start = heading.start - (1 if heading.anchor else 0)
        ranges.append((label or primary_label, path, start, heading.end, identity, reason))
        included.setdefault(identity, []).append(reason)

    def add_section(selector, reason):
        if selector not in corpus.sections:
            d.add("D06", f"target '{selector}' does not resolve", "assignment")
            return
        section = corpus.sections[selector]
        included.setdefault(selector, []).append(reason)
        if selector not in selected:
            selected.add(selector)
            add_range(section["path"], section["heading"], selector, reason)
            pending.append(selector)

    for selector in assignment["sections"]:
        add_section(selector, "assigned section")
    for selector in assignment.get("scenarios", []):
        scenario = corpus.declarations.get(selector)
        if not scenario or scenario["kind"] != "Scenario":
            d.add("D06", f"target '{selector}' does not resolve", "assignment")
            continue
        targets = {selector} | declaration_targets(corpus, scenario, "Requirements") | declaration_targets(corpus, scenario, "Tests")
        for target in list(targets):
            declaration = corpus.declarations[target]
            if declaration["kind"] == "Requirement":
                targets.update(declaration_targets(corpus, declaration, "Tests"))
        for target in sorted(targets):
            declaration = corpus.declarations[target]
            s = corpus.section_at(declaration["path"], declaration["heading"].start)
            if s:
                add_section(s["selector"], "whole scenario " + selector)
    for selector in assignment.get("decisions", []) + assignment.get("required_test_reviews", []):
        location = corpus.locate(selector)
        old_location = corpus.base.locate(selector) if corpus.base is not None and selector in assignment.get("required_test_reviews", []) else None
        if not location and not old_location:
            d.add("D06", f"target '{selector}' does not resolve", "assignment")
        if location:
            add_range(*location, selector, "decision" if selector in assignment.get("decisions", []) else "changed requirement test")
        if old_location:
            add_range(*old_location, "base:" + selector, "linked test from base snapshot", label="base")
    relevant = set()
    expanded_dependencies = set()
    while pending:
        selector = pending.pop(0)
        section = corpus.sections[selector]
        if selector not in expanded_dependencies:
            expanded_dependencies.add(selector)
            for dep in section["explanatory_dependencies"]:
                add_section(dep["section"], "declared dependency of " + selector + ": " + dep["reason"])
        md, h = corpus.markdown[section["path"]], section["heading"]
        used = {identity for identity, entity in corpus.entities.items() if entity["home"]["section"] == selector}
        for token in md.tokens:
            if token.type in ("inline", "fence", "code_block") and token.map and not any(a <= token.map[0] < b for a, b in md.generated) and h.start <= token.map[0] < h.end:
                used.update(hit[2] for hit in recognized(corpus, token.content if token.type != "inline" else visible(token.children)))
        destinations = {l.destination for l in md.links if h.start <= l.line < h.end}
        used.update(identity for identity, entity in corpus.entities.items() if destinations & use_targets(corpus, entity))
        for identity in sorted(used - relevant):
            entity = corpus.entities[identity]
            relevant.add(identity)
            home = next(h for h in corpus.markdown[entity["path"]].headings if h.anchor == entity["anchor"])
            add_range(entity["path"], home, identity, "entity owned or used in " + selector)
            # Only declared dependencies of an added home expand, not its ordinary links.
            home_section = corpus.sections[entity["home"]["section"]]
            for dep in home_section["explanatory_dependencies"]:
                add_section(dep["section"], "declared dependency of home " + identity + ": " + dep["reason"])
    for document in corpus.documents.values():
        if document.get("approval") and any(corpus.sections[s]["document"] == document["id"] for s in selected):
            selector = document["approval"]["decision"]
            location = corpus.locate(selector)
            if location:
                add_range(*location, selector, "applicable approval decision")
    for selector in assignment.get("removal_decisions", {}).values():
        location = corpus.locate(selector)
        if not location:
            d.add("D06", f"target '{selector}' does not resolve", "assignment")
        else:
            add_range(*location, selector, "requirement removal decision")
    # Merge by lines, including overlap between complete homes and assigned sections.
    merged = []
    for label, path, start, end, identity, reason in sorted(ranges):
        if merged and merged[-1]["label"] == label and merged[-1]["path"] == path and start <= merged[-1]["end"]:
            merged[-1]["end"] = max(end, merged[-1]["end"])
            merged[-1]["identities"].add(identity)
            merged[-1]["reasons"].add(reason)
        else:
            merged.append(dict(label=label, path=path, start=start, end=end, identities={identity}, reasons={reason}))
    registry_bytes = canonical(corpus.registry)
    metadata_bytes = canonical({"entities": corpus.index, "documents": corpus.manifest})
    parts = [b"# Complete registry\n\n" + registry_bytes, b"# Metadata\n\n" + metadata_bytes, b"# Applicable writing profile\n\n" + corpus.profile_bytes]
    if corpus.base is not None:
        parts.append(b"# Requirement changes (base and candidate labelled)\n\n" + canonical(requirement_changes(corpus.base, corpus).to_dict()))
    for item in merged:
        data = source_corpora[item["label"]].markdown[item["path"]].range_bytes(item["start"], item["end"])
        item["size_bytes"] = len(data)
        item["identities"] = sorted(item["identities"])
        item["reasons"] = sorted(item["reasons"])
        item["digest"] = digest(data)
        parts.append(f"# Source ({item['label']}): {item['path']}:{item['start'] + 1}-{item['end']}\n\n".encode() + data + b"\n")
    mandatory = sorted({"complete-registry", "metadata", "writing-profile", *included})
    manifest = dict(version=1, tool_version=TOOL_VERSION, format_version=corpus.contract["version"],
                    profile_version=corpus.profile["version"], label=assignment.get("label", "candidate"),
                    baseline=baseline, source_digest=corpus.source.digest, registry_digest=corpus.registry_digest,
                    input_fingerprints={p: digest(corpus.source.files[p]) for p in sorted({*JSON_PATHS, *corpus.markdown})},
                    assignment=assignment, included=mandatory, inclusion_reasons={k: sorted(set(v)) for k, v in sorted(included.items())},
                    ranges=merged, registry_size_bytes=len(registry_bytes), metadata_size_bytes=len(metadata_bytes),
                    profile_size_bytes=len(corpus.profile_bytes), profile_digest=digest(corpus.profile_bytes), size_bytes=0)
    if corpus.base is not None:
        manifest["base_provenance"] = dict(baseline=corpus.base.source.revision or corpus.base.source.digest,
                                           registry_digest=corpus.base.registry_digest,
                                           input_fingerprints={p: digest(b) for p, b in sorted(corpus.base.source.files.items())
                                                               if p in {*JSON_PATHS, *corpus.base.markdown}})
    # Size includes its own manifest. Decimal length reaches a fixed point.
    while True:
        content = b"# Context manifest\n\n" + canonical(manifest) + b"\n" + b"\n".join(parts)
        if len(content) == manifest["size_bytes"]:
            break
        manifest["size_bytes"] = len(content)
    if "budget_bytes" in assignment:
        limit = assignment["budget_bytes"]
        if type(limit) is not int or limit < 0:
            d.add("D02", "malformed declaration: budget_bytes must be nonnegative integer", "assignment")
        elif len(content) > limit:
            d.add("D25", f"mandatory pack requires {len(content)}; available budget is {limit}", "assignment")
    if d.errors:
        raise SpecDocsError(d)
    return Context(content, len(content), manifest, d)


def validate_runtime():
    """Check the runtime contract and package versions against the owning lock."""
    directory = Path(__file__).resolve().parent
    try:
        runtime = json.loads((directory / "runtime.json").read_text())
        lock = (directory / "requirements.lock").read_text()
    except (OSError, ValueError) as exc:
        fail("D27", f"cannot read tooling inputs: {exc}", "runtime", 2)
    bounds = re.fullmatch(r">=(\d+)\.(\d+),<(\d+)\.(\d+)", runtime.get("requires_python", ""))
    if runtime.get("version") != 1 or runtime.get("implementation") != "CPython" or not bounds:
        fail("D02", "unsupported runtime contract", "runtime", 2)
    minimum, maximum = tuple(map(int, bounds.groups()[:2])), tuple(map(int, bounds.groups()[2:]))
    if platform.python_implementation() != runtime["implementation"] or not minimum <= sys.version_info[:2] < maximum:
        fail("D27", f"cannot use runtime: supported interpreter is CPython {runtime['requires_python']}", "runtime", 2)
    pins = re.findall(r"^([a-zA-Z0-9_-]+)==([^\s]+)", lock, re.M)
    if {name for name, _ in pins} != {"markdown-it-py", "mdurl"} or len(pins) != 2:
        fail("D02", "malformed tooling lock: expected the two pinned parser wheels", "runtime", 2)
    for package, expected in pins:
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            actual = "missing"
        if actual != expected:
            fail("D27", f"cannot use '{package}': expected {expected}, found {actual}", "runtime", 2)


def write_outputs(corpus, outputs):
    # Validate all generated bytes as a candidate before any replacement.
    candidate_source = Snapshot(dict(corpus.source.files, **outputs), corpus.source.tracked | set(outputs),
                                corpus.source.problems, fixture=corpus.source.fixture)
    candidate = load_corpus(candidate_source, corpus.contract)
    diagnostics = check(candidate)
    if diagnostics.errors:
        raise SpecDocsError(diagnostics)
    if corpus.source.root is None:
        fail("D27", "cannot write output: snapshot has no working-tree destination", exit_code=2)
    for path, data in sorted(outputs.items()):
        target = corpus.source.root / path
        try:
            # Recheck destination components; a symlink cannot redirect a write.
            if any(p.is_symlink() for p in [target, *target.parents] if p != corpus.source.root):
                fail("D05", f"source '{path}' is outside the declared input set: symlink destination", path)
            if path == ".gitattributes" or any(doc["navigation"].get("region") and doc["navigation"]["path"] == path for doc in corpus.documents.values()):
                current = target.read_bytes() if target.exists() else None
                if current != corpus.source.files.get(path):
                    fail("D27", f"cannot replace '{path}': authored destination differs from selected snapshot", path, 2)
            target.parent.mkdir(parents=True, exist_ok=True)
            import tempfile
            fd, temporary = tempfile.mkstemp(prefix=".spec-docs-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        except OSError as exc:
            fail("D27", f"cannot write '{path}': {exc}", path, 2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "generate", "context"))
    parser.add_argument("--root", default=".")
    snapshot = parser.add_mutually_exclusive_group()
    snapshot.add_argument("--staged", action="store_true")
    snapshot.add_argument("--rev")
    parser.add_argument("--base")
    parser.add_argument("--assignment")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--format-contract", type=Path, default=REFERENCE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        validate_runtime()
        source = Snapshot.from_git(args.root, args.staged, args.rev, args.fixture)
        corpus = load_corpus(source, args.format_contract)
        assignment = None
        if args.assignment:
            assignment_diagnostics = Diagnostics()
            assignment = load_json(Path(args.assignment).read_bytes(), args.assignment, assignment_diagnostics)
            if assignment_diagnostics.errors:
                raise SpecDocsError(assignment_diagnostics, 2)
            corpus.assignment = assignment
        base = load_corpus(Snapshot.from_git(args.root, rev=args.base, fixture=args.fixture), args.format_contract, comparison=True) if args.base else None
        corpus.base = base
        if args.command == "context":
            if assignment is None:
                fail("D02", "malformed invocation: context needs --assignment", exit_code=2)
            context = select_context(corpus, assignment)
            if args.json:
                print(json.dumps(context.to_dict(), ensure_ascii=False, sort_keys=True))
            else:
                sys.stdout.buffer.write(context.content)
            return 0
        if args.command == "generate":
            outputs = generate_navigation(corpus)
            write_outputs(corpus, outputs)
            print(json.dumps({"generated": sorted(outputs)}) if args.json else "spec-docs: generated " + ", ".join(sorted(outputs)))
            return 0
        diagnostics = check(corpus, base)
        result = diagnostics.to_dict()
        if base:
            result["changes"] = requirement_changes(base, corpus).to_dict()["changes"]
        if args.json:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            for item in sorted(set(diagnostics.items)):
                print(item)
            print(f"spec-docs: {len(diagnostics.errors)} errors, {len(diagnostics.warnings)} warnings")
        return 0 if diagnostics.ok else (2 if any(d.code == "D27" for d in diagnostics.errors) else 1)
    except SpecDocsError as exc:
        if args.json:
            print(json.dumps(exc.diagnostics.to_dict(), ensure_ascii=False, sort_keys=True))
        else:
            print(str(exc), file=sys.stderr)
        return exc.exit_code
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"spec-docs: error D27 input:1: cannot process input: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

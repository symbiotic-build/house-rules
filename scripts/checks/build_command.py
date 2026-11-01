#!/usr/bin/env python3
"""Refuse a shell command that breaks the local build rules; allow everything else.

Usage: build_command.py [--debug-profile NAME] [command-file]   (standard input when absent or -)

The input is shell command text. Each simple command in it (split at unquoted `;`, `&`,
`|`, parentheses and line ends, with backslash line continuations joined, and inside
`sh -c`, `bash -c` and `zsh -c` strings) is checked:
- `cargo test` and `cargo nextest run` need a package (`-p`) and a test-name filter; an
  option value after `--` (such as `--test-threads 4` or `--skip x`) is not a filter;
  `--workspace` and `--all` are refused;
- `cargo clippy` needs a package and exactly one target (`--lib`, or one `--bin`, `--test`,
  `--example` or `--bench`); `--workspace`, `--all` and the plural target flags are refused;
- a cargo build, run, test, check, clippy or doc needs `--release`, `--profile release` or
  the debugging profile (`--profile debugging`, or the name `--debug-profile` gives); any
  other profile is refused, because the check cannot tell whether it builds with debug
  settings; `cargo bench` defaults to its release profile;
- `ctest` needs `-R`, `-L`, `-I` or `--tests-from-file`; `make`, `ninja` and
  `cmake --build` refuse the whole-suite targets `test`, `tests`, `check` and `check-all`.
Help, version, listing and dry-run calls are read-only and always allowed, as are the lookups
`command -v` and `command -V`, and any other program.

A `crate_wide_test` or `crate_wide_clippy` refusal says `"workspace": true` when the command
names no package or names `--workspace` or `--all`, so it runs across every crate.

Prints one JSON line per refusal and exits 0 when the command is allowed, 2 when it is
refused and 1 when the input cannot be read or parsed.
"""
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import findings  # noqa: E402

CHECK = "build_command"
SEPARATORS = ";&|()\n"
WRAPPERS = {"env", "time", "command", "exec", "nice", "nohup", "timeout", "caffeinate", "sudo"}
WRAPPER_VALUE_FLAGS = {"nice": {"-n"}, "timeout": {"-s", "--signal", "-k", "--kill-after"},
                       "sudo": {"-u", "-g"}, "env": {"-u", "-C", "--unset", "--chdir"}}
SHELLS = {"sh", "bash", "zsh", "dash"}
ALIASES = {"t": "test", "b": "build", "r": "run", "c": "check", "d": "doc"}
BUILDING = {"build", "run", "test", "check", "clippy", "doc", "bench", "nextest", "rustc"}
READ_ONLY_FLAGS = {"-h", "--help", "-V", "--version", "--list"}
CARGO_GLOBAL_VALUE_FLAGS = {"-C", "-Z", "--config", "--color"}
# Flags of cargo build commands that take a value; everything else that starts with `-` is a switch.
VALUE_FLAGS = {"-p", "--package", "--exclude", "--test", "--bench", "--bin", "--example", "-F", "--features",
               "--target", "--target-dir", "--profile", "-j", "--jobs", "--manifest-path", "--color",
               "--message-format", "--config", "-Z", "--lockfile-path", "--artifact-dir",
               # cargo nextest run
               "-E", "--filterset", "--filter-expr", "--partition", "--test-threads", "--retries", "-P",
               "--cargo-profile", "--run-ignored", "--archive-file", "--workspace-remap", "--tool-config-file",
               "--failure-output", "--success-output", "--status-level", "--final-status-level", "--max-fail",
               "--threads", "--build-jobs"}
# Options of the libtest harness (after `--`) that take a value.
HARNESS_VALUE_FLAGS = {"--test-threads", "--skip", "--logfile", "--format", "--color", "-Z", "--shuffle-seed",
                       "--report-time"}
SINGLE_TARGETS = ("--lib", "--bin", "--test", "--example", "--bench")
PLURAL_TARGETS = ("--all-targets", "--bins", "--tests", "--examples", "--benches")
RELEASE_PROFILES = ("release", "bench")
REDIRECTION = re.compile(r"^\d*(?:&>>?|>>?&?|<<?<?|<&|>\|)")
WHOLE_SUITE_TARGETS = {"test", "tests", "check", "check-all", "test-all", "all-tests"}


def split_commands(text):
    """Every simple command as a token list, with the input line it starts on.

    The text is split at unquoted separators; each piece is then split into words by
    `shlex`. A backslash before a line end joins the two lines, as the shell does.
    """
    result = []
    piece = []
    start = None
    line = 1
    quote = None
    index = 0

    def flush():
        nonlocal piece, start
        words = "".join(piece).strip()
        if words:
            try:
                tokens = strip_redirections(shlex.split(words))
            except ValueError as error:
                print(f"line {start}: cannot parse the command: {error}", file=sys.stderr)
                raise SystemExit(findings.INPUT_ERROR)
            if tokens:
                result.append((start, tokens))
        piece, start = [], None

    while index < len(text):
        char = text[index]
        if quote:
            piece.append(char)
            if char == "\\" and quote == '"' and index + 1 < len(text):
                piece.append(text[index + 1])
                line += text[index + 1] == "\n"
                index += 2
                continue
            if char == quote:
                quote = None
            line += char == "\n"
            index += 1
            continue
        if char == "\\" and index + 1 < len(text):
            if text[index + 1] == "\n":
                piece.append(" ")
                line += 1
            else:
                piece.extend((char, text[index + 1]))
                start = start or line
            index += 2
            continue
        if char == "#" and (not piece or piece[-1].isspace()):
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        redirection = char == "&" and ((piece and piece[-1] in "<>") or text[index + 1:index + 2] == ">")
        if char in SEPARATORS and not redirection:
            flush()
            line += char == "\n"
            index += 1
            continue
        if char in "'\"":
            quote = char
        if not char.isspace() and start is None:
            start = line
        piece.append(char)
        index += 1
    if quote:
        print(f"line {start}: cannot parse the command: no closing quotation", file=sys.stderr)
        raise SystemExit(findings.INPUT_ERROR)
    flush()
    return result


def strip_redirections(tokens):
    """The words of a command without its redirections (`2>&1`, `> out.log`, `<input`)."""
    result = []
    skip = False
    for token in tokens:
        if skip:
            skip = False
            continue
        operator = REDIRECTION.match(token)
        if operator:
            skip = operator.end() == len(token)
            continue
        result.append(token)
    return result


def unwrap(tokens):
    """The command after environment assignments and wrappers such as `env`, `time` and `nice`."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token):
            index += 1
            continue
        name = Path(token).name
        if name in WRAPPERS:
            index += 1
            values = WRAPPER_VALUE_FLAGS.get(name, set())
            while index < len(tokens) and (tokens[index].startswith("-") or
                                           re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[index])):
                if name == "command" and re.match(r"^-[a-zA-Z]*[vV]", tokens[index]):
                    return []  # `command -v` and `command -V` only look the program up
                index += 2 if tokens[index] in values else 1
            if name == "timeout" and index < len(tokens) and re.match(r"^\d+(\.\d+)?[smhd]?$", tokens[index]):
                index += 1
            continue
        break
    return tokens[index:]


def options(arguments):
    """(flags as {name: [values]}, positional arguments, arguments after `--`)."""
    flags = {}
    positional = []
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            return flags, positional, arguments[index + 1:]
        if token.startswith("--") and "=" in token:
            name, value = token.split("=", 1)
            flags.setdefault(name, []).append(value)
        elif token in VALUE_FLAGS:
            value = arguments[index + 1] if index + 1 < len(arguments) else ""
            flags.setdefault(token, []).append(value)
            index += 1
        elif re.match(r"^-[pjFEZP].+", token):
            flags.setdefault(token[:2], []).append(token[2:])
        elif token.startswith("-"):
            flags.setdefault(token, []).append(None)
        else:
            positional.append(token)
        index += 1
    return flags, positional, []


def refusal(rule, message, number, tokens, **detail):
    return findings.finding(CHECK, rule, message, number, command=shlex.join(tokens), **detail)


def check_cargo(number, tokens, arguments, debug_profile):
    index = 0
    while index < len(arguments) and (arguments[index].startswith("-") or arguments[index].startswith("+")):
        if arguments[index] in READ_ONLY_FLAGS:
            return []
        index += 2 if arguments[index] in CARGO_GLOBAL_VALUE_FLAGS else 1
    if index >= len(arguments):
        return []
    subcommand = ALIASES.get(arguments[index], arguments[index])
    rest = arguments[index + 1:]
    if subcommand == "nextest":
        if not rest or rest[0] != "run":
            return []
        rest = rest[1:]
    if subcommand not in BUILDING:
        return []
    flags, positional, trailing = options(rest)
    if any(flag in flags for flag in READ_ONLY_FLAGS) or "--list" in trailing:
        return []
    result = []
    package = "-p" in flags or "--package" in flags
    whole = "--workspace" in flags or "--all" in flags
    if subcommand in ("test", "nextest"):
        filtered = any(positional) or bool(harness_filters(trailing)) or \
            any(any(flags.get(flag, [])) for flag in ("-E", "--filterset", "--filter-expr"))
        if whole or not package:
            result.append(refusal("crate_wide_test", f"cargo {subcommand} without a package runs every crate's "
                                  "tests; name one with -p and add a test-name filter", number, tokens,
                                  workspace=True))
        elif not filtered and "--no-run" not in flags:
            result.append(refusal("crate_wide_test", f"cargo {subcommand} without a test-name filter runs the "
                                  "crate's whole suite; add the filter, for example --test <file> <test_name>",
                                  number, tokens, workspace=False))
    if subcommand == "clippy":
        selected = sum(len(flags.get(flag, [])) for flag in SINGLE_TARGETS)
        plural = any(flag in flags for flag in PLURAL_TARGETS)
        if whole or not package or plural or selected != 1:
            result.append(refusal("crate_wide_clippy", "cargo clippy needs a package (-p) and exactly one target "
                                  "(--lib, or one --bin, --test, --example or --bench); crate-wide clippy runs in CI",
                                  number, tokens, workspace=whole or not package))
    profile_flag = "--cargo-profile" if subcommand == "nextest" else "--profile"
    allowed = RELEASE_PROFILES + (debug_profile,)
    profiles = flags.get(profile_flag, [])
    other = [profile for profile in profiles if profile not in allowed]
    if other:
        result.append(refusal("debug_build", f"profile {other[0]!r} is neither a release profile nor the debugging "
                              f"profile {debug_profile!r}; use --release, or {profile_flag} {debug_profile} while "
                              "actively debugging", number, tokens))
    elif subcommand != "bench" and not profiles and "--release" not in flags and "-r" not in flags:
        result.append(refusal("debug_build", f"cargo {subcommand} without --release builds the debug profile; "
                              f"add --release, or use {profile_flag} {debug_profile} while actively debugging",
                              number, tokens))
    return result


def harness_filters(arguments):
    """The test-name filters among the test harness arguments after `--`, without option values."""
    result = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in HARNESS_VALUE_FLAGS:
            index += 2
            continue
        if argument and not argument.startswith("-"):
            result.append(argument)
        index += 1
    return result


def check_ctest(number, tokens, arguments):
    flags, _, _ = options(arguments)
    if any(flag in flags for flag in ("-N", "--show-only", "-h", "--help", "--version")):
        return []
    selected = any(re.match(r"^(-R|-L|-I|--tests-regex|--label-regex|--tests-information|--tests-from-file)", arg)
                   for arg in arguments)
    if selected:
        return []
    return [refusal("whole_suite", "ctest without -R, -L or -I runs the whole suite; select the tests that "
                    "prove the change", number, tokens)]


def check_targets(number, tokens, tool, arguments):
    read_only = {"make": ("-n", "--dry-run", "--just-print", "--recon", "-q", "--question", "-h", "--help",
                          "-v", "--version"),
                 "ninja": ("-n", "-t", "-h", "--help", "--version")}[tool]
    if any(arg in read_only or (tool == "ninja" and arg.startswith("-t")) for arg in arguments):
        return []
    targets = [arg for arg in arguments if not arg.startswith("-") and "=" not in arg]
    hits = [target for target in targets if target in WHOLE_SUITE_TARGETS]
    if not hits:
        return []
    return [refusal("whole_suite", f"{tool} {hits[0]} runs the whole test suite; run the targeted test instead",
                    number, tokens)]


def check_cmake(number, tokens, arguments):
    if "--build" not in arguments:
        return []
    targets = []
    collecting = False
    for arg in arguments:
        if arg == "--":
            break
        if arg in ("--target", "-t"):
            collecting = True
        elif arg.startswith("--target="):
            targets.extend(arg.split("=", 1)[1].split(","))
            collecting = True
        elif arg.startswith("-"):
            collecting = False
        elif collecting:
            targets.extend(arg.split(","))
    hits = [target for target in targets if target in WHOLE_SUITE_TARGETS]
    if not hits:
        return []
    return [refusal("whole_suite", f"cmake --build --target {hits[0]} runs the whole test suite; run the "
                    "targeted test instead", number, tokens)]


def check_command(number, tokens, debug_profile):
    command = unwrap(tokens)
    if not command:
        return []
    name = Path(command[0]).name
    arguments = command[1:]
    if name in SHELLS:
        for index, arg in enumerate(arguments):
            if arg == "-c" or (arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]):
                if index + 1 < len(arguments):
                    return check(arguments[index + 1], debug_profile, number)
        return []
    if name == "cargo":
        return check_cargo(number, tokens, arguments, debug_profile)
    if name == "ctest":
        return check_ctest(number, tokens, arguments)
    if name in ("make", "gmake", "ninja"):
        return check_targets(number, tokens, "ninja" if name == "ninja" else "make", arguments)
    if name == "cmake":
        return check_cmake(number, tokens, arguments)
    return []


def check(text, debug_profile="debugging", line=None):
    result = []
    for number, tokens in split_commands(text):
        result.extend(check_command(line or number, tokens, debug_profile))
    return result


def main(argv=None):
    parser = findings.parser(__doc__.splitlines()[0])
    parser.add_argument("--debug-profile", default="debugging", help="the cargo profile allowed for debugging")
    args = parser.parse_args(argv)
    return findings.finish(check(findings.read_text(args.path), args.debug_profile))


if __name__ == "__main__":
    sys.exit(main())

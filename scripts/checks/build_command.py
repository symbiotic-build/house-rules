#!/usr/bin/env python3
"""Refuse a shell command that breaks the local build rules; allow everything else.

Usage: build_command.py [--debug-profile NAME] [command-file]   (standard input when absent or -)

The input is shell command text. Each simple command in it (split at `;`, `&&`, `||`, `|`,
`&` and line ends, and inside `sh -c`, `bash -c` and `zsh -c` strings) is checked:
- `cargo test` and `cargo nextest run` need a package (`-p`) and a test-name filter;
  `--workspace` and `--all` are refused;
- `cargo clippy` needs a package and a target (`--lib`, `--bin`, `--test`, `--example`,
  `--bench`); `--workspace`, `--all` and `--all-targets` are refused;
- a cargo build, run, test, check, clippy or doc needs `--release` or a profile other than
  the debug one; a debug build needs the debugging profile (`--profile debugging`, or the
  name `--debug-profile` gives);
- `ctest` needs `-R`, `-L`, `-I` or `--tests-from-file`; `make`, `ninja` and
  `cmake --build` refuse the whole-suite targets `test`, `tests`, `check` and `check-all`.
Help, version, listing and dry-run calls are read-only and always allowed, as is any other
program.

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
SEPARATORS = {";", "&&", "||", "|", "&", "|&", ";;", "(", ")"}
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
WHOLE_SUITE_TARGETS = {"test", "tests", "check", "check-all", "test-all", "all-tests"}


def split_commands(text):
    """Every simple command as a token list, with its input line number."""
    result = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        try:
            tokens = list(lexer)
        except ValueError as error:
            print(f"line {number}: cannot parse the command: {error}", file=sys.stderr)
            raise SystemExit(findings.INPUT_ERROR)
        current = []
        for token in tokens:
            if token in SEPARATORS:
                if current:
                    result.append((number, current))
                current = []
            else:
                current.append(token)
        if current:
            result.append((number, current))
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


def refusal(rule, message, number, tokens):
    return findings.finding(CHECK, rule, message, number, command=shlex.join(tokens))


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
        filtered = bool(positional) or any(not item.startswith("-") for item in trailing) or \
            "-E" in flags or "--filterset" in flags or "--filter-expr" in flags
        if whole or not package:
            result.append(refusal("crate_wide_test", f"cargo {subcommand} without a package runs every crate's "
                                  "tests; name one with -p and add a test-name filter", number, tokens))
        elif not filtered and "--no-run" not in flags:
            result.append(refusal("crate_wide_test", f"cargo {subcommand} without a test-name filter runs the "
                                  "crate's whole suite; add the filter, for example --test <file> <test_name>",
                                  number, tokens))
    if subcommand == "clippy":
        targets = any(flag in flags for flag in ("--lib", "--bin", "--test", "--example", "--bench"))
        if whole or not package or "--all-targets" in flags or not targets:
            result.append(refusal("crate_wide_clippy", "cargo clippy needs a package (-p) and one target "
                                  "(--lib, --bin, --test, --example or --bench); crate-wide clippy runs in CI",
                                  number, tokens))
    if subcommand != "bench":
        profile_flag = "--cargo-profile" if subcommand == "nextest" else "--profile"
        profiles = flags.get(profile_flag, [])
        release = "--release" in flags or "-r" in flags or any(p not in ("dev", "test", "") for p in profiles)
        if not release:
            result.append(refusal("debug_build", f"cargo {subcommand} without --release builds the debug profile; "
                                  f"add --release, or use {profile_flag} {debug_profile} while actively debugging",
                                  number, tokens))
    elif any(p in ("dev", "test") for p in flags.get("--profile", [])):
        result.append(refusal("debug_build", f"cargo bench on the debug profile; use --profile {debug_profile} "
                              "while actively debugging", number, tokens))
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
    for index, arg in enumerate(arguments):
        if arg in ("--target", "-t") and index + 1 < len(arguments):
            targets.extend(arguments[index + 1].split(","))
        elif arg.startswith("--target="):
            targets.extend(arg.split("=", 1)[1].split(","))
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

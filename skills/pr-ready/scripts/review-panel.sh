#!/usr/bin/env bash
# Run a read-only review panel in parallel.
# Usage: review-panel.sh [--rev COMMIT] [--repo DIR] [--session] [--assignment JSON] <name> <checkout> <base-prompt> [reviewer ...]
# Pin: --rev or REVIEW_HOUSE_RULES_REV is required; --repo or REVIEW_HOUSE_RULES_REPO names the clone.
#   name: [A-Za-z0-9][A-Za-z0-9._-]*, a single directory name
#   reviewer: a file stem in ../../../prompts/lenses/ (default: generalist-<family> for each configured family)
# Config: ${REVIEW_PANEL_CONF:-<house-rules>/custom/review-panel.conf}, lines "<family> = <cli> <model> [tier] [effort]",
#   cli one of codex | grok | kimi. Unconfigured families are omitted from the default selection.
# Prompt order: role rules, lens, summary/task, spec, change (prepare.py review).
# Range: ${REVIEW_BASE:-remote default branch}...HEAD; upstream preferred to origin.
# Output directory: ${REVIEW_PANEL_OUT:-<checkout>/.tmp/review-panel}/<name>/ with <reviewer>.md,
#   raw logs, and summary.txt (verdict and wall time per reviewer).
set -u
here=$(cd "$(dirname "$0")" && pwd)
rules_repo=${REVIEW_HOUSE_RULES_REPO:-$here/../../..}
rules_rev=${REVIEW_HOUSE_RULES_REV:-}
session_mode=0
assignment=${REVIEW_SPEC_ASSIGNMENT:-}
review_python=${REVIEW_PYTHON:-python3}
while [ $# -gt 0 ]; do
  case $1 in
    --rev|--repo|--assignment)
      [ $# -ge 2 ] || { echo "$1 requires a value" >&2; exit 2; }
      case $1 in --rev) rules_rev=$2 ;; --repo) rules_repo=$2 ;; --assignment) assignment=$2 ;; esac
      shift 2 ;;
    --session) session_mode=1; shift ;;
    *) break ;;
  esac
done
[ $# -ge 3 ] || { echo "expected name, checkout and task file" >&2; exit 2; }
conf=${REVIEW_PANEL_CONF:-$here/../../../custom/review-panel.conf}
name=$1
dir=$(cd "$2" && pwd) || exit 2
review_rev=$(git --no-replace-objects -C "$dir" rev-parse --verify --end-of-options 'HEAD^{commit}') || exit 2
base=$(cd "$(dirname "$3")" && pwd)/$(basename "$3"); shift 3
output_root=${REVIEW_PANEL_OUT:-$dir/.tmp/review-panel}
out=$output_root/$name
family_cfg() { sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$conf" 2>/dev/null | head -1; }

if [ $# -eq 0 ]; then
  for f in a b c; do [ -n "$(family_cfg $f)" ] && set -- "$@" "generalist-$f"; done
fi
[ $# -gt 0 ] || { echo "no reviewers: configure families in $conf" >&2; exit 2; }

# Validate the whole panel before creating or writing any output.
# Resolve symlinks as well as '..'; a lexical prefix check is not containment.
python3 -I -B - "$rules_repo" "$rules_rev" "$output_root" "$name" "$@" <<'PY' || exit 2
from pathlib import Path
import re
import subprocess
import sys

repo, rev, output_root, name, *reviewers = sys.argv[1:]
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
    sys.exit(f"invalid panel name: {name!r}; expected [A-Za-z0-9][A-Za-z0-9._-]*")
if len(reviewers) != len(set(reviewers)):
    sys.exit("duplicate reviewer names are not allowed")
for reviewer in reviewers:
    if not re.fullmatch(r"[a-z0-9-]+", reviewer):
        sys.exit(f"invalid reviewer: {reviewer!r}; expected [a-z0-9-]+")

try:
    root = Path(output_root).resolve()
    panel = (root / name).resolve()
    if panel == root or not panel.is_relative_to(root):
        sys.exit(f"refusing panel directory outside output root: {panel}")
except (OSError, RuntimeError) as exc:
    sys.exit(f"cannot validate panel directory: {exc}")
if not rev:
    sys.exit("review panel requires --rev COMMIT or REVIEW_HOUSE_RULES_REV")
try:
    pin = subprocess.run(["git", "--no-replace-objects", "-C", repo, "rev-parse", "--verify",
                          "--end-of-options", rev + "^{commit}"], capture_output=True, timeout=5, check=True).stdout.decode().strip()
    for reviewer in reviewers:
        path = f"prompts/lenses/{reviewer}.md"
        entry = subprocess.run(["git", "--no-replace-objects", "-C", repo, "ls-tree", "-z", pin,
                                "--", path], capture_output=True, timeout=5, check=True).stdout
        if not entry or entry.split(b"\t", 1)[-1] != path.encode() + b"\0" or entry[:6] not in (b"100644", b"100755"):
            sys.exit(f"invalid reviewer: {reviewer!r}; no matching regular reviewer file at {pin[:12]}")
except (OSError, subprocess.SubprocessError) as exc:
    sys.exit(f"cannot read panel pin: {exc}")
PY
rules_rev=$(git --no-replace-objects -C "$rules_repo" rev-parse --verify --end-of-options "$rules_rev^{commit}") || exit 2
mkdir -p "$output_root" || exit 1
mkdir "$out" || { echo "review panel requires a fresh panel directory: $out" >&2; exit 1; }

: > "$out/summary.txt" || exit 1
git --no-replace-objects -C "$rules_repo" show "$rules_rev:skills/pr-ready/scripts/prompt.py" > "$out/compiler.py" || exit 2
git --no-replace-objects -C "$rules_repo" show "$rules_rev:skills/pr-ready/scripts/prepare.py" > "$out/preparer.py" || exit 2
git --no-replace-objects -C "$rules_repo" show "$rules_rev:skills/pr-ready/scripts/review-panel.lenses" > "$out/lenses.conf" || exit 2

base_args=(base "$dir")
[ -n "${REVIEW_BASE:-}" ] && base_args+=(--base "$REVIEW_BASE")
resolved_base=$(python3 -I -B "$here/prepare.py" "${base_args[@]}") || {
  echo "panel failed: base resolution" >> "$out/summary.txt"
  exit 1
}

run_one() {
  local r=$1
  local fam sandbox settings cfg cli model tier effort prompt=$out/$r.prompt t0 cli_status=0 verdict
  if ! settings=$(python3 -I -B "$here/prepare.py" lens "$r" --config "$out/lenses.conf"); then
    echo "$r failed: lens configuration" >> "$out/summary.txt"
    return 1
  fi
  read -r fam sandbox <<<"$settings"
  cfg=$(family_cfg "$fam")
  [ -n "$cfg" ] || { echo "$r failed: family $fam not configured" >> "$out/summary.txt"; return 1; }
  read -r cli model tier effort <<<"$cfg"; [ "$tier" = - ] && tier=
  local prepare_args=(review "$dir" --rev "$review_rev" --context-only --lens "$r" --cli "$cli" --summary "$base" --base "$resolved_base" --no-fetch)
  # Keep one compilation in memory for both task budgeting and final publication.
  if ! "$review_python" -I -B - "$out" "$rules_repo" "$rules_rev" "$dir" "$review_rev" "$r" "$session_mode" "$cli" \
      "$assignment" "${prepare_args[@]}" 2> "$out/$r.prepare.err" <<'PY'
from contextlib import redirect_stdout
from pathlib import Path
import sys
import subprocess

out, repo, rev, checkout, review_rev, reviewer, session, cli, assignment, *args = sys.argv[1:]
sys.path.insert(0, out)
from compiler import Commit, PromptError, append_tasks, build_pack, publish
from preparer import main as prepare_main

try:
    with Commit(repo, rev) as source, Commit(checkout, review_rev) as target:
        pack, manifest = build_pack(source, role="reviewer", lens=reviewer, target=target,
                                    omit_shared_rules=session == "1",
                                    assignment=Path(assignment).read_bytes() if assignment else None)
    # Check Git readers before preparing context or publishing any artifacts.
    if cli == "codex":
        args += ["--compiled-chars", str(len(pack.decode("utf-8")) + 1)]
    task = Path(out) / (reviewer + ".task")
    with task.open("w", encoding="utf-8") as stream, redirect_stdout(stream):
        status = prepare_main(args, documentation_prepared="documentation" in manifest)
    if status:
        sys.exit(2)
    pack, manifest = append_tasks(pack, manifest, [(task, "review-panel-" + reviewer)])
    publish(Path(out) / (reviewer + ".pack"), pack, manifest)
except (PromptError, OSError, UnicodeError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
    print("prompt: " + " ".join(str(exc).splitlines()), file=sys.stderr)
    sys.exit(2)
PY
  then
    cat "$out/$r.prepare.err" >&2
    echo "$r failed: context preparation or prompt compilation (see $r.prepare.err)" >> "$out/summary.txt"
    return 1
  fi
  if ! python3 -I -B "$here/prepare.py" check-prompt "$out/$r.pack/pack.txt" --cli "$cli" 2>> "$out/$r.prepare.err"; then
    cat "$out/$r.prepare.err" >&2
    echo "$r failed: complete prompt size (see $r.prepare.err)" >> "$out/summary.txt"
    return 1
  fi
  ln -s "$r.pack/pack.txt" "$prompt" || return 1
  cat "$out/$r.prepare.err" >&2
  sed -n '/^# 3\. Pull request and issue/q; /^Size guard:/p' "$out/$r.task" |
    while IFS= read -r notice; do printf '%s: %s\n' "$r" "$notice"; done >> "$out/summary.txt"
  t0=$(date +%s)
  # Transient provider errors (capacity, overload, rate limits) are retried twice, 60 s apart;
  # any other failure fails the reviewer at once.
  local attempt logs input_hashes current_hashes
  input_hashes=$(shasum -a 256 "$out/$r.pack/pack.txt" "$out/$r.pack/manifest.json") || return 1
  for attempt in 1 2 3; do
    current_hashes=$(shasum -a 256 "$out/$r.pack/pack.txt" "$out/$r.pack/manifest.json") || return 1
    if [ "$current_hashes" != "$input_hashes" ]; then
      echo "$r failed: pack or manifest changed before attempt $attempt; attempts=$((attempt - 1))" >> "$out/summary.txt"
      return 1
    fi
    logs=$out/$r.attempt-$attempt
    cli_status=0
    case $cli in
      codex) codex exec --json --skip-git-repo-check -m "$model" -c model_reasoning_effort="${effort:-high}" \
               ${tier:+-c service_tier="\"$tier\""} -s "$sandbox" -C "$dir" -o "$logs.md" - < "$prompt" \
               > "$logs.jsonl" 2> "$logs.err" || cli_status=$? ;;
      # Grok has no read-only sandbox that starts on every host, so the reviewer gets only read tools:
    # no shell (which could reach authenticated gh/git), no file writes, no MCP. Names are Grok's runtime
    # tool names (checked in the session's tool_definitions.json), not the older documented ones.
    grok)  # Grok discovers project configuration (.mcp.json, hooks) from its working directory, and a
           # change under review can edit that configuration. Run it from an empty directory instead and
           # let it read the checkout by absolute path.
           local neutral; neutral=$(mktemp -d "${TMPDIR:-/tmp}/review-grok.XXXXXX") || return 1
           if ! (cd "$neutral" && env GROK_CLAUDE_AGENTS_ENABLED=0 GROK_CLAUDE_SKILLS_ENABLED=0 GROK_CLAUDE_RULES_ENABLED=0 \
               GROK_CLAUDE_MCPS_ENABLED=0 GROK_CLAUDE_HOOKS_ENABLED=0 GROK_CURSOR_AGENTS_ENABLED=0 \
               GROK_CURSOR_SKILLS_ENABLED=0 GROK_CURSOR_RULES_ENABLED=0 grok inspect 2>&1) | python3 -I -B -c '
import re, sys
# Fail closed: every MCP server and hook Grok would load for this run must be disabled.
text = sys.stdin.read(); ok = True; seen = set()
for section in ("MCP Servers", "Hooks"):
    m = re.search(r"^  " + section + r" \((\d+)\)\n((?:  \u2514 .*\n)*)", text, re.M)
    if not m: sys.exit(f"grok inspect: no {section} section")
    seen.add(section)
    for line in m.group(2).splitlines():
        if "(none)" not in line and "[disabled]" not in line:
            print(f"enabled {section}: {line.strip()}", file=sys.stderr); ok = False
sys.exit(0 if ok else 1)' 2>> "$logs.err"; then
             echo "$r failed: Grok would load an enabled hook or MCP server (see $r.attempt-$attempt.err); attempts=$attempt" >> "$out/summary.txt"; return 1
           fi
           (cd "$neutral" && env GROK_CLAUDE_AGENTS_ENABLED=0 GROK_CLAUDE_SKILLS_ENABLED=0 GROK_CLAUDE_RULES_ENABLED=0 \
               GROK_CLAUDE_MCPS_ENABLED=0 GROK_CLAUDE_HOOKS_ENABLED=0 GROK_CURSOR_AGENTS_ENABLED=0 \
               GROK_CURSOR_SKILLS_ENABLED=0 GROK_CURSOR_RULES_ENABLED=0 \
               grok -m "$model" --reasoning-effort "${effort:-high}" --tools read_file,list_dir,grep --output-format json --always-approve --disable-web-search --prompt-file "$prompt" > "$logs.json" 2>> "$logs.err") || cli_status=$?
           rmdir "$neutral" 2>/dev/null
             if [ "$cli_status" -eq 0 ]; then
               python3 -I -B "$here/grok_final.py" "$logs.json" > "$logs.md" 2>> "$logs.err" || cli_status=$?
             fi ;;
      kimi)  # Python preserves the pack's trailing newlines in the CLI argument.
             /usr/bin/python3 -I -B -c '
from pathlib import Path
import subprocess, sys
checkout, model, prompt = sys.argv[1:]
text = Path(prompt).read_bytes().decode("utf-8")
sys.exit(subprocess.run(["kimi", "-m", model, "-p", text], cwd=checkout).returncode)
' "$dir" "$model" "$prompt" > "$logs.md" 2> "$logs.err" || cli_status=$? ;;
      *)     echo "$r failed: unknown cli $cli" >> "$out/summary.txt"; return 1 ;;
    esac
    [ "$cli_status" -ne 0 ] && [ $attempt -lt 3 ] && cat "$logs.err" "$logs.jsonl" "$logs.json" 2>/dev/null |
      grep -q -i -E 'at capacity|overloaded|rate.?limit|too many requests|\b429\b|\b503\b' || break
    echo "$r: transient provider error on attempt $attempt; retrying in 60 s" >> "$out/summary.txt"
    sleep 60
  done
  ln -s "$r.attempt-$attempt.md" "$out/$r.md" || return 1
  if [ "$cli_status" -ne 0 ]; then
    echo "$r failed: reviewer CLI (exit $cli_status; see $r.attempt-$attempt.err); attempts=$attempt" >> "$out/summary.txt"
    return 1
  fi
  if ! verdict=$(python3 -I -B "$here/verdict.py" "$logs.md" 2>> "$logs.err"); then
    echo "$r failed: reviewer report missing valid VERDICT: APPROVE or VERDICT: REQUEST_CHANGES token (see $r.md and $r.attempt-$attempt.err); attempts=$attempt" >> "$out/summary.txt"
    return 1
  fi
  echo "$r $cli/$model wall=$(( $(date +%s) - t0 ))s attempts=$attempt verdict=$verdict" >> "$out/summary.txt"
}

python3 -I -B "$here/review-panel-models.py" --check >&2 || true   # notice only: newer models available
pids=()
for r in "$@"; do
  run_one "$r" &
  pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do wait "$pid" || status=1; done
transient_inputs=("$out/lenses.conf" "$out/preparer.py")
for r in "$@"; do transient_inputs+=("$out/$r.task"); done
if ! rm -f -- "${transient_inputs[@]}"; then
  echo "panel failed: removing temporary compilation inputs" >> "$out/summary.txt"
  status=1
fi
[ -n "$(git -C "$dir" status --porcelain)" ] && echo "WARNING: a reviewer modified the checkout" >> "$out/summary.txt"
cat "$out/summary.txt"
exit "$status"

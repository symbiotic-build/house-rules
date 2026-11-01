#!/usr/bin/env python3
"""Classify a failure record or a text, and say whether only the operator can clear it.

Usage: blocker_classify.py [input]   (standard input when absent or -)

The input is one JSON object, a JSON array of objects, JSON lines, or plain text. Fields
read from an object (every other field is ignored, so a proxy journal line or a job record
can be passed as it is):
- `category`: the failure category a review service gives a failed job;
- `reason`: that failure's reason text;
- `failure`: an object holding `category` and `reason`, as a job record nests them;
- `record`: an object holding the fields above, as an exported job record wraps them;
- `status`: the provider's HTTP status, a number or a string of digits;
- `code`: the provider's error code;
- `provider_message`: the provider's error text;
- `provider`, else `route`, else `family`: the name used in the action text;
- `text`: free text, for example an operator message or a question.

Prints one JSON line per input: `index`, `class`, `operator_only`, `action` (the exact step
to take), `field` and `matched` (the evidence). Exits 2 when any input is operator-only, so
a caller stops and puts that action first; 0 when none is; 1 when the input cannot be read.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import findings  # noqa: E402

CHECK = "blocker_classify"
OPERATOR_ONLY = ("credential", "account", "balance", "quota", "permission", "protected_asset")


def rule(name, pattern, action):
    return name, re.compile(pattern, re.IGNORECASE), action


# Text rules, in precedence order: operator-only classes first, because a provider can wrap an
# account gate in a throttle or a policy refusal ("top up your balance to restore your
# concurrency", a policy code whose message names a hardware key).
TEXT_RULES = [
    rule("credential", r"hardware[- ]keys?|security keys?|passkeys?",
         "Sign in to {provider} again with an authorized hardware key, then tell the agent the session is "
         "authenticated."),
    rule("credential", r"not authenticated|unauthenticated|re-?authenticat\w*|\bre-?auth\b|login (has )?expired|"
         r"session (has )?expired|token (has )?expired|expired (token|credential|login|session)|invalid[ _]api[ _]key|"
         r"incorrect api key|authentication (failed|required|error)|\bunauthori[sz]ed\b|sign in again|log ?in again|"
         r"\b(auth|authentication|login|log-in|sign-in) page\b",
         "Sign in to {provider} again or replace its credential, then tell the agent the credential is ready."),
    rule("balance", r"insufficient[ _](balance|credit|funds)|\btop[- ]?up\b|out of credits?|no credits? (left|remaining)|"
         r"credit balance is too low|balance (is )?(empty|exhausted|too low|insufficient|zero)|payment required|"
         r"billing[ _](hard[ _])?limit",
         "Top up the {provider} account balance, then tell the agent the balance is restored."),
    rule("quota", r"usage limit|\b(weekly|monthly|daily) (usage )?(limit|quota)|insufficient[ _]quota|quota (exceeded|"
         r"exhausted|will reset|reached)|exceeded (your|the) (current )?quota|upgrade (your|the) plan|"
         r"purchase extra usage",
         "Buy more {provider} usage or upgrade the plan, or tell the agent to wait until the quota window resets."),
    rule("account", r"account gate|account (is |has been )?(suspended|disabled|locked|deactivated|banned|closed|restricted)|"
         r"organi[sz]ation (is |has been )?(disabled|suspended)|verify your (account|organi[sz]ation|identity)|"
         r"accept the terms",
         "Resolve the {provider} account state in its console, then tell the agent the account is usable."),
    rule("permission", r"permission denied|(missing|lacks?|without|needs?) (the |a |an )?([\w:-]+ ){0,2}permissions?\b|"
         r"insufficient (permissions?|scopes?)|not permitted|access denied|resource not accessible|"
         r"requires? (the )?[\w:-]+ scope",
         "Grant the missing permission or scope to the agent's {provider} identity, then tell the agent it is "
         "granted."),
    rule("protected_asset", r"\bvouchers?\b|banked reset|one-time credit|subscription (change|upgrade)|"
         r"(rotate|revoke) (the |a |an )?([\w-]+ )?(key|credential|token)|"
         r"\b(create|generate|issue|mint) (a |an |the )?(new )?([\w-]+ ){0,2}(keys?|tokens?|credentials?|secrets?)\b",
         "Confirm or perform this protected-asset action yourself; the agent does not consume or change it "
         "without your confirmation."),
    rule("rate_limit", r"too many requests|rate[- _]limit\w*|slow down|overloaded|concurrency limit",
         "Retry after the provider's delay; no operator step."),
    rule("timeout", r"time limit|timed out|time-?out|deadline exceeded",
         "Find why the job ran past its limit; raise the limit only with a measured reason. No operator step."),
    rule("policy_refusal", r"cyber[_ -]?policy|content policy|safety policy|usage polic(y|ies)|refused the request",
         "Change the request or the model; no operator step. Read the provider message first: an account gate "
         "can arrive as a policy refusal."),
    rule("provider_error", r"internal server error|bad gateway|service unavailable|upstream connect error",
         "Retry; if it repeats, report the provider outage. No operator step."),
    rule("network", r"connection (refused|reset)|could not resolve|name resolution|network is unreachable",
         "Check the route to the provider; no operator step."),
]
CODES = {
    "insufficient_quota": "quota",
    "invalid_api_key": "credential",
    "billing_hard_limit_reached": "balance",
    "rate_limit_exceeded": "rate_limit",
    "cyber_policy": "policy_refusal",
    "content_policy_violation": "policy_refusal",
}
CATEGORIES = {
    "refusal": "policy_refusal",
    "runtime_limit": "timeout",
    "model": "job_failure",
}
# The action for a class found from a code, a status or a category. A text rule carries its own
# action, which can be more exact (the hardware-key rule names the key).
ACTIONS = {name: action for name, _, action in reversed(TEXT_RULES)}
ACTIONS["credential"] = TEXT_RULES[1][2]
ACTIONS["job_failure"] = "Read the job's logs and fix the cause; no operator step."
ACTIONS["unknown"] = "Read the record; no rule matched it. Escalate only after the cause is known."
ACTIONS["none"] = "No failure or blocker is named; no operator step."


def status_class(status):
    """The class a bare HTTP status gives, read only from the status field."""
    if status == 401:
        return "credential"
    if status == 402:
        return "balance"
    if status == 403:
        return "permission"
    if status == 429:
        return "rate_limit"
    if status in (408, 504):
        return "timeout"
    if 500 <= status <= 599:
        return "provider_error"
    return None


def as_status(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def fields(record):
    """The fields the classifier reads, from a flat, nested or wrapped record."""
    if isinstance(record.get("record"), dict):
        record = {**record["record"], **{k: v for k, v in record.items() if k != "record"}}
    failure = record.get("failure") if isinstance(record.get("failure"), dict) else {}
    provider = next((record[key] for key in ("provider", "route", "family")
                     if isinstance(record.get(key), str) and record[key]), None)
    return {
        "category": record.get("category") or failure.get("category"),
        "reason": record.get("reason") or failure.get("reason"),
        "status": as_status(record.get("status")),
        "code": record.get("code"),
        "provider_message": record.get("provider_message"),
        "text": record.get("text"),
        "provider": provider,
    }


def text_class(texts):
    """(class, matched text, action, field) for the first text rule that matches any text, else None.

    `texts` is a list of (field, text). Rule order decides first and field order breaks a tie,
    so an ordinary failure in one field cannot hide an operator-only blocker in another.
    """
    for name, pattern, action in TEXT_RULES:
        for field, text in texts:
            match = pattern.search(text)
            if match:
                return name, match.group(0), action, field
    return None


def operator_only_mentions(text):
    """Every (class, matched text, offset) of an operator-only class named anywhere in a text."""
    result = []
    for name, pattern, _ in TEXT_RULES:
        if name not in OPERATOR_ONLY:
            continue
        for match in pattern.finditer(text):
            result.append((name, match.group(0), match.start()))
    return sorted(result, key=lambda item: item[2])


def classify(record):
    """The classification of one record: class, operator_only, action, field and matched."""
    values = fields(record)
    name = matched = field = action = None
    hit = text_class([(key, values[key]) for key in ("provider_message", "text", "reason")
                      if isinstance(values[key], str) and values[key]])
    if hit:
        name, matched, action, field = hit
    if name is None and isinstance(values["code"], str) and values["code"] in CODES:
        name, matched, field = CODES[values["code"]], values["code"], "code"
    if name is None and values["status"] is not None and status_class(values["status"]):
        name, matched, field = status_class(values["status"]), values["status"], "status"
    if name is None and values["category"] in CATEGORIES:
        name, matched, field = CATEGORIES[values["category"]], values["category"], "category"
    if name is None:
        only_text = values["text"] is not None and all(
            values[key] is None for key in ("category", "reason", "status", "code", "provider_message"))
        name = "none" if only_text else "unknown"
    provider = values["provider"] or "the provider"
    return {
        "class": name,
        "operator_only": name in OPERATOR_ONLY,
        "action": (action or ACTIONS[name]).replace("{provider}", provider),
        "field": field,
        "matched": matched,
    }


def parse(text):
    """The input records: a JSON object, a JSON array, JSON lines, or one plain-text record."""
    stripped = text.strip()
    try:
        value = json.loads(stripped)
    except ValueError:
        value = None
    else:
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            return value
        value = None
    records = []
    for line in stripped.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            return [{"text": text}]
        if not isinstance(item, dict):
            return [{"text": text}]
        records.append(item)
    return records or [{"text": text}]


def main(argv=None):
    args = findings.parser(__doc__.splitlines()[0]).parse_args(argv)
    results = []
    for index, record in enumerate(parse(findings.read_text(args.path))):
        results.append({"check": CHECK, "index": index, **classify(record)})
    return findings.finish(results, failed=any(result["operator_only"] for result in results))


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Record changes to rule files, skills and prompts in a ledger, and roll one change back.

The ledger is `ledger.jsonl` in the installation state folder: `$XDG_STATE_HOME/house-rules`,
by default `~/.local/state/house-rules`. Each line is one record:

  id          12 hexadecimal characters
  time        UTC time of the change, ISO 8601
  action      change | rollback
  actor       human | agent | service
  file        absolute path of the changed file
  before      sha256 of the content before the change, or null when the file did not exist
  after       sha256 of the content after the change, or null when the change removed the file
  reason      why the file changed
  source_pr   the pull request the change came from, or null
  rollback_of the id of the record a rollback reverted (rollback records only)
  commit      the commit that made the change (records of merged changes only)

Every before and after content is stored under its hash in `ledger-blobs/` beside the ledger,
so any record can be reverted. A rollback restores the record's before content and appends a
rollback record whose before is the content it replaced, so a rollback can be rolled back too.

  rules_ledger.py write FILE --actor KIND --reason TEXT [--pr REF] < CONTENT
  rules_ledger.py rollback ID [--actor KIND] [--reason TEXT]
  rules_ledger.py list
"""
import argparse
import contextlib
import datetime
try:
    import fcntl
except ImportError:  # native Windows
    fcntl = None
    import msvcrt
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys

ACTORS = ("human", "agent", "service")


def state_dir():
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "house-rules"


def ledger_path():
    return state_dir() / "ledger.jsonl"


def blob_path(digest):
    return state_dir() / "ledger-blobs" / digest


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def create(path, data):
    """Write a new file readable only by its owner, so private content never shows on the way."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def store(data):
    """Store data under its sha256 and return the hash; None stands for an absent file."""
    if data is None:
        return None
    digest = hashlib.sha256(data).hexdigest()
    path = blob_path(digest)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{digest}.{secrets.token_hex(4)}")
        create(temporary, data)
        os.replace(temporary, path)
    return digest


def load(digest):
    if digest is None:
        return None
    data = blob_path(digest).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"stored content {digest} does not match its hash")
    return data


def read(path):
    try:
        return Path(path).read_bytes()
    except FileNotFoundError:
        return None


def put(path, data):
    """Write data to path atomically, or remove path when data is None."""
    path = Path(path)
    if data is None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        mode = path.stat().st_mode & 0o7777
    else:  # a new file gets the mode any new file gets
        mask = os.umask(0)
        os.umask(mask)
        mode = 0o666 & ~mask
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}")
    create(temporary, data)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


@contextlib.contextmanager
def locked():
    """Hold the ledger lock, which serializes every reader-then-writer of the ledger."""
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name("ledger.lock"), "a+b") as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
            return
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def entries():
    try:
        text = ledger_path().read_text()
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def new_record(file, before, after, actor, reason, source_pr=None, **extra):
    if actor not in ACTORS:
        raise ValueError(f"actor must be one of {', '.join(ACTORS)}, not {actor!r}")
    if not reason:
        raise ValueError("a change needs a reason")
    return {"id": secrets.token_hex(6), "time": now(), "action": "change", "actor": actor,
            "file": str(file), "before": store(before), "after": store(after), "reason": reason,
            "source_pr": source_pr, **extra}


def append(records):
    """Append records to the ledger. The caller holds the lock."""
    with open(ledger_path(), "a") as ledger:
        for record in records:
            ledger.write(json.dumps(record, ensure_ascii=False) + "\n")
        ledger.flush()
        os.fsync(ledger.fileno())


def apply(file, data, record):
    """Write the file, then append its record; restore the file when the append fails."""
    previous = read(file)
    put(file, data)
    try:
        append([record])
    except BaseException:
        put(file, previous)
        raise
    return record


def write(file, data, actor, reason, source_pr=None):
    """Change file to data through the ledger; None when the content is already data."""
    file = Path(file).resolve()
    with locked():
        before = read(file)
        if before == data:
            return None
        return apply(file, data, new_record(file, before, data, actor, reason, source_pr))


def rollback(entry_id, actor="human", reason=None):
    """Restore the before content of one record and append a rollback record."""
    with locked():
        target = next((record for record in entries() if record["id"] == entry_id), None)
        if target is None:
            raise ValueError(f"no ledger record {entry_id}")
        restored = load(target["before"])
        current = read(target["file"])
        if store(current) != target["after"]:
            print(f"NOTE: {target['file']} changed after record {entry_id}; the rollback record "
                  "keeps that later content as its before", file=sys.stderr)
        record = new_record(target["file"], current, restored, actor,
                            reason or f"roll back {entry_id}: {target['reason']}",
                            target.get("source_pr"), rollback_of=entry_id)
        record["action"] = "rollback"
        return apply(target["file"], restored, record)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    change = commands.add_parser("write", help="replace FILE with standard input and record the change")
    change.add_argument("file")
    change.add_argument("--actor", required=True, choices=ACTORS)
    change.add_argument("--reason", required=True)
    change.add_argument("--pr", help="the source pull request")
    revert = commands.add_parser("rollback", help="restore the before content of one record")
    revert.add_argument("id")
    revert.add_argument("--actor", default="human", choices=ACTORS)
    revert.add_argument("--reason")
    commands.add_parser("list", help="print every record, oldest first")
    args = parser.parse_args(argv)
    try:
        if args.command == "write":
            record = write(args.file, sys.stdin.buffer.read(), args.actor, args.reason, args.pr)
            print(f"RECORDED: {record['id']} {record['file']}" if record else "UNCHANGED: no record")
        elif args.command == "rollback":
            record = rollback(args.id, args.actor, args.reason)
            print(f"ROLLED BACK: {args.id} as {record['id']} {record['file']}")
        else:
            for record in entries():
                print(f"{record['id']} {record['time']} {record['action']} {record['actor']} "
                      f"{record['file']}: {record['reason'].splitlines()[0]}")
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

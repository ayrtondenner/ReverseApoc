"""A stand-in for the real attempt wrapper that the driver's broker runs in the tests (owner
rule: no test runs Docker; the broker's real wrapper is `uv run --frozen reverseapoc attempt`).

`python tests/fakewrapper.py ARGS...` (ARGS: what follows `attempt`):

1. exits 64 when REVERSEAPOC_WRAPPER_BROKER is set (the broker must run the wrapper without
   it) or the cwd is not REVERSEAPOC_ATTEMPT_DIR (the broker runs it in the attempt dir);
2. FAKEWRAPPER_RECORD (a file path): appends {"args", "cwd", "env": [names]} as one JSON line,
   the environment as its variable NAMES only;
3. FAKEWRAPPER_SLEEP: then sleeps that many seconds (a long check, a stop or a timeout);
4. `context` writes <attempt dir>/context.md; `check` appends the line FAKEWRAPPER_CHECK (JSON;
   default a passing check) to checks.jsonl and writes checks/0001.note.json (FAKEWRAPPER_NOTE,
   JSON); each written file's sha256 is appended to REVERSEAPOC_WRAPPER_LEDGER, as the real
   wrapper's _ledgered does;
5. prints `fake wrapper: ARGS` to stdout and `fake wrapper stderr` to stderr and exits 0, or
   the check line's exit for `check`.

It imports no tool module. Nothing here is a game byte.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

BAD_ENV = 64
BROKER_ENV = "REVERSEAPOC_WRAPPER_BROKER"
DIR_ENV = "REVERSEAPOC_ATTEMPT_DIR"
LEDGER_ENV = "REVERSEAPOC_WRAPPER_LEDGER"
RECORD_ENV = "FAKEWRAPPER_RECORD"
SLEEP_ENV = "FAKEWRAPPER_SLEEP"
CHECK_ENV = "FAKEWRAPPER_CHECK"
NOTE_ENV = "FAKEWRAPPER_NOTE"
PASSING = {"n": 1, "exit": 0, "sweep": False, "best_percent": 100.0, "reloc_ok": True,
           "bytes_ok": True, "splice_ok": True, "sweep_hit": None, "source": "checks/0001.c",
           "note": "checks/0001.note.json"}  # fmt: skip
NOTE = {"change": "made up", "why": "made up", "expect": "made up"}


def _write(attempt_dir: Path, rel: str, text: str, *, append: bool = False) -> None:
    path = attempt_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a" if append else "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    ledger = os.environ.get(LEDGER_ENV)
    if ledger:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with Path(ledger).open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"path": rel, "sha256": digest}, sort_keys=True) + "\n")


def main(argv: list[str]) -> int:
    attempt_dir = Path(os.environ.get(DIR_ENV, ""))
    if os.environ.get(BROKER_ENV) or Path.cwd().resolve() != attempt_dir.resolve():
        print(f"fakewrapper: {BROKER_ENV} set or cwd {Path.cwd()} is not {attempt_dir}",
              file=sys.stderr)  # fmt: skip
        return BAD_ENV
    record = os.environ.get(RECORD_ENV)
    if record:
        with Path(record).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"args": argv, "cwd": str(Path.cwd()),
                                 "env": sorted(os.environ)}) + "\n")  # fmt: skip
    time.sleep(float(os.environ.get(SLEEP_ENV) or 0))
    code = 0
    if argv == ["context"]:
        _write(attempt_dir, "context.md", "made-up pack rebuilt by the wrapper\n")
    elif argv == ["check"]:
        line = json.loads(os.environ.get(CHECK_ENV) or json.dumps(PASSING))
        _write(attempt_dir, "checks.jsonl", json.dumps(line) + "\n", append=True)
        _write(attempt_dir, "checks/0001.note.json",
               json.dumps(json.loads(os.environ.get(NOTE_ENV) or json.dumps(NOTE))) + "\n")
        code = int(line["exit"])
    print(f"fake wrapper: {' '.join(argv)}")
    print("fake wrapper stderr", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

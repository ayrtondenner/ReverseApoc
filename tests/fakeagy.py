"""A stand-in for the Antigravity CLI `agy` in the driver tests (owner rule: no test runs the real
agy).

`python tests/fakeagy.py --output-format stream-json --model M --sandbox --add-dir DIR
--settings FILE --disable-slash-commands --print-timeout Ns -p PROMPT` takes exactly that argv,
in that order (session.build_agy_argv after the executable), and:

1. checks the shape: every flag above in its place, N a positive integer with the `s` unit (agy
   parses a Go duration and exits on a bare number), a non-empty model and
   PROMPT, and never `--dangerously-skip-permissions`; any other argv exits 64 naming what
   differs;
2. FAKEAGY_RECORD (a file path): writes {"argv": [...], "env": [names], "cwd": ...} there, the
   environment as its variable NAMES only, so no value (and never a credential) is written;
3. replays tests/fixtures/agy/NAME.jsonl to stdout, flushing after every line, the way
   `agy -p --output-format stream-json` streams; NAME is FAKEAGY_SCENARIO ([a-z0-9_]+, no path
   can be spelled). Each line is agy 1.5.5's envelope, {"event": kind, kind: {...}}; in an
   `init` event's payload, a `cwd` of "@cwd" becomes this process's working directory and a
   `model` of "@model" the --model value, as the real CLI reports them; every other line is
   written byte for byte;
4. replays tests/fixtures/agy/NAME.stderr to stderr, byte for byte, when that file exists
   (headless agy names a permission it auto-denied there and nowhere else, spike 012);
5. exits 0.

It imports no tool module. The fixtures hold synthetic events only, never game bytes.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "agy"
_SCENARIO = re.compile(r"[a-z0-9_]+")
_SECONDS = re.compile(r"[1-9][0-9]*s")  # agy 1.5.5 parses a Go duration: a bare number exits
SCENARIO_ENV = "FAKEAGY_SCENARIO"
RECORD_ENV = "FAKEAGY_RECORD"
BAD_ARGV = 64
BANNED = "--dangerously-skip-permissions"
_FIXED = {0: "--output-format", 1: "stream-json", 2: "--model", 4: "--sandbox", 5: "--add-dir",
          7: "--settings", 9: "--disable-slash-commands", 10: "--print-timeout",
          12: "-p"}  # fmt: skip
_MODEL, _TIMEOUT, _PROMPT = 3, 11, 13
_LENGTH = _PROMPT + 1
_CWD, _MODEL_SLOT = "@cwd", "@model"


def _problem(argv: list[str]) -> str | None:
    if BANNED in argv:
        return f"{BANNED} is never passed"
    if len(argv) != _LENGTH:
        return f"{len(argv)} arguments, expected {_LENGTH}"
    for index, token in _FIXED.items():
        if argv[index] != token:
            return f"argument {index} is {argv[index]!r}, expected {token!r}"
    if not _SECONDS.fullmatch(argv[_TIMEOUT]):
        return f"--print-timeout {argv[_TIMEOUT]!r} is not a whole number of seconds like 1800s"
    if not argv[_MODEL] or not argv[_PROMPT]:
        return "an empty model or prompt"
    return None


def _line(raw: bytes, model: str) -> bytes:
    try:
        event = json.loads(raw)
    except ValueError:
        return raw
    init = event.get("init") if isinstance(event, dict) and event.get("event") == "init" else None
    if not isinstance(init, dict):
        return raw
    if init.get("cwd") == _CWD:
        init["cwd"] = os.getcwd()
    if init.get("model") == _MODEL_SLOT:
        init["model"] = model
    return (json.dumps(event) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    problem = _problem(argv)
    if problem is not None:
        print(f"fakeagy: {problem}", file=sys.stderr)
        return BAD_ARGV
    record = os.environ.get(RECORD_ENV)
    if record:
        Path(record).write_text(json.dumps({"argv": argv, "env": sorted(os.environ),
                                            "cwd": os.getcwd()}), encoding="utf-8")  # fmt: skip
    name = os.environ.get(SCENARIO_ENV, "")
    path = FIXTURES / f"{name}.jsonl"
    if not _SCENARIO.fullmatch(name) or not path.is_file():
        print(f"fakeagy: no scenario {name!r}", file=sys.stderr)
        return BAD_ARGV
    out = sys.stdout.buffer
    for raw in path.read_bytes().splitlines(keepends=True):
        out.write(_line(raw, argv[_MODEL]))
        out.flush()
    err = path.with_suffix(".stderr")
    if err.is_file():
        sys.stderr.buffer.write(err.read_bytes())
        sys.stderr.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())

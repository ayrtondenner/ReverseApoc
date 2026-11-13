"""A stand-in for the GitHub Copilot CLI `copilot` in the driver tests (owner rule: no test runs
the real copilot).

`python tests/fakecopilot.py -p PROMPT --model M ...` takes the argv session.build_copilot_argv
builds after the executable and:

1. checks the shape: `-p` and a non-empty PROMPT first; every flag of FIXED with its value;
   `--available-tools` followed by exactly the copilotjson tool set; `--max-ai-credits` a whole
   number of at least 30; `--usage-output-file` an absolute path; and none of BANNED (the
   allow-everything flags, autopilot, a trusted folder, an added directory, memory); any other
   argv exits 64 naming what differs;
2. FAKECOPILOT_RECORD (a file path): writes {"argv": [...], "env": [names], "cwd": ...} there,
   the environment as its variable NAMES only, so no value (and never a credential) is written;
3. replays tests/fixtures/copilot/NAME.jsonl to stdout, flushing after every line, the way
   `copilot -p --output-format json` streams; NAME is FAKECOPILOT_SCENARIO ([a-z0-9_]+, no path
   can be spelled). In every string of a line, `@cwd` becomes this process's working directory,
   `@parent` the directory above it, `@repo` the checkout (UV_PROJECT, which the driver
   sets), `@unit` and `@notes` the session's view unit and notes file (their REVERSEAPOC_* variables) and `@model` the --model value, all
   with forward slashes; a string that is exactly `@credits` becomes the --max-ai-credits
   number. A line that starts with a UTF-8 BOM keeps it (Copilot CLI 1.0.111 writes one on its
   first line);
4. writes tests/fixtures/copilot/NAME.usage.json, slots filled the same way, to the
   --usage-output-file path when that fixture exists (else writes nothing there);
5. exits 0.

It imports no tool module. The fixtures hold synthetic events only, never game bytes.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "copilot"
_SCENARIO = re.compile(r"[a-z0-9_]+")
SCENARIO_ENV = "FAKECOPILOT_SCENARIO"
RECORD_ENV = "FAKECOPILOT_RECORD"
BAD_ARGV = 64
BOM = b"\xef\xbb\xbf"
FIXED = {"--model": None, "--output-format": "json", "--stream": "on"}
FLAGS = ("--no-auto-update", "--no-custom-instructions", "--disable-builtin-mcps",
         "--no-ask-user", "--disallow-temp-dir")  # fmt: skip
TOOLS = ["view", "create", "edit", "powershell", "read_powershell"]
BANNED = ("--allow-all", "--yolo", "--allow-all-tools", "--allow-all-paths", "--allow-all-urls",
          "--autopilot", "--trust-folder", "--add-dir", "--enable-memory",
          "--assisted-approval")  # fmt: skip
MIN_CREDITS = 30


def _value(argv: list[str], flag: str) -> str | None:
    return argv[argv.index(flag) + 1] if flag in argv[:-1] else None


def _problem(argv: list[str]) -> str | None:
    if len(argv) < 2 or argv[0] != "-p" or not argv[1]:
        return "`-p PROMPT` does not come first"
    rest = argv[2:]
    banned = [flag for flag in BANNED if flag in rest]
    if banned:
        return f"{banned[0]} is never passed"
    for flag, want in FIXED.items():
        got = _value(rest, flag)
        if got is None or (want is not None and got != want):
            return f"{flag} is {got!r}, expected {want or 'a value'!r}"
    missing = [flag for flag in FLAGS if flag not in rest]
    if missing:
        return f"{missing[0]} is missing"
    if "--available-tools" not in rest:
        return "--available-tools is missing"
    start = rest.index("--available-tools") + 1
    if rest[start:start + len(TOOLS)] != TOOLS or (
            start + len(TOOLS) < len(rest) and not rest[start + len(TOOLS)].startswith("--")):
        return f"--available-tools is not exactly {TOOLS}"
    credits = _value(rest, "--max-ai-credits") or ""
    if not credits.isdigit() or int(credits) < MIN_CREDITS:
        return f"--max-ai-credits {credits!r} is not a whole number of at least {MIN_CREDITS}"
    usage = _value(rest, "--usage-output-file") or ""
    if not os.path.isabs(usage):
        return f"--usage-output-file {usage!r} is not an absolute path"
    return None


def _slots(argv: list[str]) -> dict[str, str]:
    def slashed(text: str) -> str:
        return text.replace("\\", "/")

    return {"@cwd": slashed(os.getcwd()), "@parent": slashed(os.path.dirname(os.getcwd())),
            "@repo": slashed(os.environ.get("UV_PROJECT", "")),
            "@unit": slashed(os.environ.get("REVERSEAPOC_UNIT_FILE", "")),
            "@notes": slashed(os.environ.get("REVERSEAPOC_ATTEMPT_NOTES", "")),
            "@model": _value(argv, "--model") or ""}  # fmt: skip


def _filled(value: object, slots: dict[str, str], credits: int) -> object:
    if isinstance(value, dict):
        return {key: _filled(item, slots, credits) for key, item in value.items()}
    if isinstance(value, list):
        return [_filled(item, slots, credits) for item in value]
    if value == "@credits":
        return credits
    if not isinstance(value, str):
        return value
    for slot, text in slots.items():
        value = value.replace(slot, text)
    return value


def _line(raw: bytes, slots: dict[str, str], credits: int) -> bytes:
    bom = raw.startswith(BOM)
    try:
        event = json.loads(raw[len(BOM):] if bom else raw)
    except ValueError:
        return raw
    return (BOM if bom else b"") + (json.dumps(_filled(event, slots, credits)) + "\n").encode()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    problem = _problem(argv)
    if problem is not None:
        print(f"fakecopilot: {problem}", file=sys.stderr)
        return BAD_ARGV
    record = os.environ.get(RECORD_ENV)
    if record:
        Path(record).write_text(json.dumps({"argv": argv, "env": sorted(os.environ),
                                            "cwd": os.getcwd()}), encoding="utf-8")  # fmt: skip
    name = os.environ.get(SCENARIO_ENV, "")
    path = FIXTURES / f"{name}.jsonl"
    if not _SCENARIO.fullmatch(name) or not path.is_file():
        print(f"fakecopilot: no scenario {name!r}", file=sys.stderr)
        return BAD_ARGV
    slots, credits = _slots(argv), int(_value(argv, "--max-ai-credits"))
    out = sys.stdout.buffer
    for raw in path.read_bytes().splitlines(keepends=True):
        out.write(_line(raw, slots, credits))
        out.flush()
    usage = FIXTURES / f"{name}.usage.json"
    if usage.is_file():
        doc = _filled(json.loads(usage.read_text(encoding="utf-8")), slots, credits)
        Path(_value(argv, "--usage-output-file")).write_text(json.dumps(doc), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

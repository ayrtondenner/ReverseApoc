"""A stand-in for the `claude` CLI in the driver tests (owner rule: no test runs the real claude).

`python tests/fakeclaude.py --scenario NAME [--env-unit-paths [--any-unit]] [--model M]
[--init-model M] [--write PATH] [--write-env-unit TEXT] [--spawn-child] [--sleep S] [--exit N]`
does, in this order:

1. replays tests/fixtures/stream/NAME.jsonl to stdout, byte for byte, flushing after every line,
   the way `claude -p --output-format stream-json` streams. `--env-unit-paths` (07-13, D-24):
   when REVERSEAPOC_UNIT_FILE is set, a write tool's `file_path` that names the same
   `src/<exe>/<unit>.c` as that view unit is replayed as the view unit's path instead (one
   re-serialised line), as a session that edits the unit its /goal names would write it; every
   other line stays byte for byte, and without the variable nothing changes. `--any-unit`
   (07-21, workers): a path naming any `src/<exe>/<unit>.c` is replayed as the view unit, so
   the one stream fixture serves sessions claiming other units. `--model M` (07-30, D-09): the
   init event's `model` is replayed as M, the model the session was asked for, as the real CLI
   echoes its `--model`; `--init-model M` forces that string instead (a CLI answering a request
   with another model). Without either the init line stays byte for byte;
2. `--write PATH`: writes a small made-up C file at PATH, resolved against its own cwd (ruling
   F11), creating parent directories, as an agent's edit would. `--write-env-unit TEXT` writes
   TEXT to the file REVERSEAPOC_UNIT_FILE names (the driver's view unit, D-24); exit 3 when the
   variable is unset;
3. `--spawn-child`: starts a child process that sleeps, and once the child reports its own pid,
   emits `{"type":"system","subtype":"fake_child","pid":N}` so a test can check the child is
   gone after a tree kill (ruling F34);
4. `--sleep S`: sleeps S seconds;
5. exits with `--exit N` (default 0).

The fixtures hold synthetic events only, never game bytes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stream"
_SCENARIO = re.compile(r"[a-z0-9_]+")  # a fixture stem; no path can be spelled
WRITTEN = "/* written by tests/fakeclaude.py */\nint fake_written;\n"
UNIT_FILE_ENV = "REVERSEAPOC_UNIT_FILE"  # hooks.UNIT_FILE_ENV, spelled out: no tool import here
NO_UNIT_FILE = 3  # --write-env-unit without the variable
_EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
_INIT = ("system", "init")
CHILD_SLEEP_S = 120  # far longer than any test's wall clock
_CHILD = f"import os, time; print(os.getpid(), flush=True); time.sleep({CHILD_SLEEP_S})"


def _scenario(name: str) -> Path:
    if not _SCENARIO.fullmatch(name):
        raise argparse.ArgumentTypeError(f"bad scenario name {name!r}")
    path = FIXTURES / f"{name}.jsonl"
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"no fixture {path.name}")
    return path


def _emit(out, line: bytes) -> None:
    out.write(line)
    out.flush()


def _spawn_child() -> int:
    """Start the sleeping child (it inherits this process's group, so a tree kill reaches it)
    and return the pid it reports for itself."""
    child = subprocess.Popen(
        [sys.executable, "-I", "-c", _CHILD],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return int(child.stdout.readline())


def _unit_tail(path: str) -> str | None:
    """`src/<exe>/<unit>.c` of a path, forward slashes, or None when it has no such tail."""
    parts = path.replace("\\", "/").split("/")
    if len(parts) < 3 or parts[-3] != "src" or not parts[-1].endswith(".c"):
        return None
    return "/".join(parts[-3:])


def _retarget(line: bytes, unit_file: str, *, any_unit: bool = False) -> bytes:
    """`line` with every write tool's file_path naming the view unit's `src/<exe>/<unit>.c`
    (with `any_unit`: any such path) replaced by `unit_file`; any other line (or one that is
    not JSON) is returned unchanged."""
    want = _unit_tail(unit_file)
    try:
        event = json.loads(line)
    except ValueError:
        return line
    content = event.get("message", {}).get("content") if isinstance(event, dict) else None
    changed = False
    for block in content if isinstance(content, list) else ():
        tool_input = block.get("input") if isinstance(block, dict) else None
        if block.get("name") not in _EDIT_TOOLS or not isinstance(tool_input, dict):
            continue
        path = tool_input.get("file_path")
        tail = _unit_tail(path) if isinstance(path, str) else None
        if want is not None and tail is not None and (any_unit or tail == want):
            tool_input["file_path"] = unit_file
            changed = True
    if not changed:
        return line
    return json.dumps(event, separators=(",", ":")).encode("utf-8") + b"\n"


def _init_model(line: bytes, model: str) -> bytes:
    """`line` with the init event's `model` set to `model`; any other line is unchanged."""
    try:
        event = json.loads(line)
    except ValueError:
        return line
    if not isinstance(event, dict) or (event.get("type"), event.get("subtype")) != _INIT:
        return line
    event["model"] = model
    return json.dumps(event, separators=(",", ":")).encode("utf-8") + b"\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fakeclaude", description=__doc__)
    parser.add_argument("--scenario", type=_scenario, required=True)
    parser.add_argument("--env-unit-paths", action="store_true")
    parser.add_argument("--any-unit", action="store_true")
    parser.add_argument("--model", metavar="M")
    parser.add_argument("--init-model", metavar="M")
    parser.add_argument("--write", type=Path)
    parser.add_argument("--write-env-unit", metavar="TEXT")
    parser.add_argument("--spawn-child", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--exit", type=int, default=0)
    args = parser.parse_args(argv)
    unit_file = os.environ.get(UNIT_FILE_ENV)
    if args.write_env_unit is not None and not unit_file:
        print(f"fakeclaude: --write-env-unit needs {UNIT_FILE_ENV}", file=sys.stderr)
        return NO_UNIT_FILE
    out = sys.stdout.buffer
    init_model = args.init_model or args.model
    for line in args.scenario.read_bytes().splitlines(keepends=True):
        if args.env_unit_paths and unit_file:
            line = _retarget(line, unit_file, any_unit=args.any_unit)
        if init_model is not None:
            line = _init_model(line, init_model)
        _emit(out, line)
    if args.write is not None:
        target = Path.cwd() / args.write
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(WRITTEN, encoding="utf-8", newline="\n")
    if args.write_env_unit is not None:
        target = Path(unit_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(args.write_env_unit, encoding="utf-8", newline="\n")
    if args.spawn_child:
        event = {"type": "system", "subtype": "fake_child", "pid": _spawn_child()}
        _emit(out, json.dumps(event).encode() + b"\n")
    if args.sleep:
        time.sleep(args.sleep)
    return args.exit


if __name__ == "__main__":
    sys.exit(main())

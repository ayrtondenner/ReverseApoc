"""A stand-in for the `claude` CLI in the driver tests (owner rule: no test runs the real claude).

`python tests/fakeclaude.py --scenario NAME [--write PATH] [--spawn-child] [--sleep S] [--exit N]`
does, in this order:

1. replays tests/fixtures/stream/NAME.jsonl to stdout, byte for byte, flushing after every line,
   the way `claude -p --output-format stream-json` streams;
2. `--write PATH`: writes a small made-up C file at PATH, resolved against its own cwd (ruling
   F11), creating parent directories, as an agent's edit would;
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
import re
import subprocess
import sys
import time
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stream"
_SCENARIO = re.compile(r"[a-z0-9_]+")  # a fixture stem; no path can be spelled
WRITTEN = "/* written by tests/fakeclaude.py */\nint fake_written;\n"
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fakeclaude", description=__doc__)
    parser.add_argument("--scenario", type=_scenario, required=True)
    parser.add_argument("--write", type=Path)
    parser.add_argument("--spawn-child", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--exit", type=int, default=0)
    args = parser.parse_args(argv)
    out = sys.stdout.buffer
    for line in args.scenario.read_bytes().splitlines(keepends=True):
        _emit(out, line)
    if args.write is not None:
        target = Path.cwd() / args.write
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(WRITTEN, encoding="utf-8", newline="\n")
    if args.spawn_child:
        event = {"type": "system", "subtype": "fake_child", "pid": _spawn_child()}
        _emit(out, json.dumps(event).encode() + b"\n")
    if args.sleep:
        time.sleep(args.sleep)
    return args.exit


if __name__ == "__main__":
    sys.exit(main())

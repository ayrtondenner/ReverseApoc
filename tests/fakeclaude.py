"""A stand-in for the `claude` CLI in the driver tests (owner rule: no test runs the real claude).

`python tests/fakeclaude.py --scenario NAME` replays tests/fixtures/stream/NAME.jsonl to stdout,
byte for byte, flushing after every line, the way `claude -p --output-format stream-json`
streams. The fixtures hold synthetic events only, never game bytes.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stream"
_SCENARIO = re.compile(r"[a-z0-9_]+")  # a fixture stem; no path can be spelled


def _scenario(name: str) -> Path:
    if not _SCENARIO.fullmatch(name):
        raise argparse.ArgumentTypeError(f"bad scenario name {name!r}")
    path = FIXTURES / f"{name}.jsonl"
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"no fixture {path.name}")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fakeclaude", description=__doc__)
    parser.add_argument("--scenario", type=_scenario, required=True)
    args = parser.parse_args(argv)
    out = sys.stdout.buffer
    for line in args.scenario.read_bytes().splitlines(keepends=True):
        out.write(line)
        out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())

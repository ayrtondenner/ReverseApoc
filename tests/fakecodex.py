"""A stand-in for the `codex` CLI in the driver tests (owner rule: no test runs the real codex).

`python tests/fakecodex.py exec --json --model M --sandbox workspace-write --cd DIR
--skip-git-repo-check --ephemeral --ignore-user-config -c approval_policy="never"
-c sandbox_workspace_write.network_access=false -c windows.sandbox="elevated"
-c projects."DIR".trust_level="trusted" PROMPT`
takes exactly that argv, in that order (session.build_codex_argv after the executable), and:

1. checks the shape: every flag above in its place, DIR twice the same, a non-empty PROMPT
   last; any other argv exits 64 naming what differs;
2. FAKECODEX_RECORD (a file path): writes {"argv": [...], "env": [names]} there, the
   environment as its variable NAMES only, so no value (and never a credential) is written;
3. replays tests/fixtures/codex/NAME.jsonl to stdout, byte for byte, flushing after every
   line, the way `codex exec --json` streams; NAME is FAKECODEX_SCENARIO ([a-z0-9_]+, no path
   can be spelled);
4. exits 0.

It imports no tool module. The fixtures hold synthetic events only, never game bytes.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "codex"
_SCENARIO = re.compile(r"[a-z0-9_]+")
SCENARIO_ENV = "FAKECODEX_SCENARIO"
RECORD_ENV = "FAKECODEX_RECORD"
BAD_ARGV = 64
_FIXED = {0: "exec", 1: "--json", 2: "--model", 4: "--sandbox", 5: "workspace-write", 6: "--cd",
          8: "--skip-git-repo-check", 9: "--ephemeral", 10: "--ignore-user-config", 11: "-c",
          12: 'approval_policy="never"', 13: "-c",
          14: "sandbox_workspace_write.network_access=false", 15: "-c",
          16: 'windows.sandbox="elevated"', 17: "-c"}  # fmt: skip
_TRUST = 18
_PROMPT = _TRUST + 1
_LENGTH = _PROMPT + 1  # the fixed tokens, the model, DIR, the trust entry and the prompt


def _problem(argv: list[str]) -> str | None:
    if len(argv) != _LENGTH:
        return f"{len(argv)} arguments, expected {_LENGTH}"
    for index, token in _FIXED.items():
        if argv[index] != token:
            return f"argument {index} is {argv[index]!r}, expected {token!r}"
    trust = f"projects.{json.dumps(argv[7])}.trust_level=\"trusted\""
    if argv[_TRUST] != trust:
        return f"the trust entry {argv[_TRUST]!r} is not {trust!r}"
    if not argv[3] or not argv[_PROMPT]:
        return "an empty model or prompt"
    return None


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    problem = _problem(argv)
    if problem is not None:
        print(f"fakecodex: {problem}", file=sys.stderr)
        return BAD_ARGV
    record = os.environ.get(RECORD_ENV)
    if record:
        Path(record).write_text(json.dumps({"argv": argv, "env": sorted(os.environ)}),
                                encoding="utf-8")  # fmt: skip
    name = os.environ.get(SCENARIO_ENV, "")
    path = FIXTURES / f"{name}.jsonl"
    if not _SCENARIO.fullmatch(name) or not path.is_file():
        print(f"fakecodex: no scenario {name!r}", file=sys.stderr)
        return BAD_ARGV
    out = sys.stdout.buffer
    for line in path.read_bytes().splitlines(keepends=True):
        out.write(line)
        out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())

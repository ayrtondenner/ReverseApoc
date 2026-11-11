"""A stand-in for the `codex` CLI in the driver tests (owner rule: no test runs the real codex).

`python tests/fakecodex.py exec --json --model M --sandbox workspace-write --cd DIR
--skip-git-repo-check --ephemeral --ignore-user-config -c approval_policy="never"
-c sandbox_workspace_write.network_access=false -c windows.sandbox="unelevated"
-c projects."DIR".trust_level="trusted" PROMPT`
takes exactly that argv, in that order (session.build_codex_argv after the executable), and:

1. checks the shape: every flag above in its place, DIR twice the same, a non-empty PROMPT
   last; any other argv exits 64 naming what differs;
2. FAKECODEX_CALLS (a JSON list of argument lists, each what follows `attempt`): runs the real
   attempt wrapper's client for each, in DIR (Codex's --cd) with this process's environment
   (`python -m reverseapoc.cli attempt ARGS`, what `uv run --frozen reverseapoc` starts), as a
   Codex session's command would; with REVERSEAPOC_WRAPPER_BROKER set the client queues its
   request for the driver's broker and waits for the response;
3. FAKECODEX_RECORD (a file path): writes {"argv": [...], "env": [names], "calls": [{"args",
   "exit", "stdout", "stderr"}]} there, the environment as its variable NAMES only, so no value
   (and never a credential) is written;
4. replays tests/fixtures/codex/NAME.jsonl to stdout, byte for byte, flushing after every
   line, the way `codex exec --json` streams; NAME is FAKECODEX_SCENARIO ([a-z0-9_]+, no path
   can be spelled);
5. replays tests/fixtures/codex/NAME.stderr to stderr, byte for byte, when that file exists
   (the real CLI names each command its policy rejected there and nowhere else);
6. exits 0.

It imports no tool module (the client runs in a child process). The fixtures hold synthetic
events only, never game bytes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "codex"
_SCENARIO = re.compile(r"[a-z0-9_]+")
SCENARIO_ENV = "FAKECODEX_SCENARIO"
RECORD_ENV = "FAKECODEX_RECORD"
CALLS_ENV = "FAKECODEX_CALLS"
CALL_TIMEOUT_S = 120  # one client call, broker round trip included
BAD_ARGV = 64
_FIXED = {0: "exec", 1: "--json", 2: "--model", 4: "--sandbox", 5: "workspace-write", 6: "--cd",
          8: "--skip-git-repo-check", 9: "--ephemeral", 10: "--ignore-user-config", 11: "-c",
          12: 'approval_policy="never"', 13: "-c",
          14: "sandbox_workspace_write.network_access=false", 15: "-c",
          16: 'windows.sandbox="unelevated"', 17: "-c"}  # fmt: skip
_DIR = 7  # DIR, the --cd value
_TRUST = 18
_PROMPT = _TRUST + 1
_LENGTH = _PROMPT + 1  # the fixed tokens, the model, DIR, the trust entry and the prompt


def _problem(argv: list[str]) -> str | None:
    if len(argv) != _LENGTH:
        return f"{len(argv)} arguments, expected {_LENGTH}"
    for index, token in _FIXED.items():
        if argv[index] != token:
            return f"argument {index} is {argv[index]!r}, expected {token!r}"
    trust = f"projects.{json.dumps(argv[_DIR])}.trust_level=\"trusted\""
    if argv[_TRUST] != trust:
        return f"the trust entry {argv[_TRUST]!r} is not {trust!r}"
    if not argv[3] or not argv[_PROMPT]:
        return "an empty model or prompt"
    return None


def _call(args: list[str], cwd: str) -> dict:
    """One wrapper command as a Codex session runs it: the client in Codex's --cd."""
    done = subprocess.run([sys.executable, "-m", "reverseapoc.cli", "attempt", *args], cwd=cwd,
                          capture_output=True, text=True, timeout=CALL_TIMEOUT_S,
                          check=False)  # fmt: skip
    return {"args": args, "exit": done.returncode, "stdout": done.stdout, "stderr": done.stderr}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    problem = _problem(argv)
    if problem is not None:
        print(f"fakecodex: {problem}", file=sys.stderr)
        return BAD_ARGV
    calls = [_call(args, argv[_DIR]) for args in json.loads(os.environ.get(CALLS_ENV) or "[]")]
    record = os.environ.get(RECORD_ENV)
    if record:
        Path(record).write_text(json.dumps({"argv": argv, "env": sorted(os.environ),
                                            "calls": calls}), encoding="utf-8")  # fmt: skip
    name = os.environ.get(SCENARIO_ENV, "")
    path = FIXTURES / f"{name}.jsonl"
    if not _SCENARIO.fullmatch(name) or not path.is_file():
        print(f"fakecodex: no scenario {name!r}", file=sys.stderr)
        return BAD_ARGV
    out = sys.stdout.buffer
    for line in path.read_bytes().splitlines(keepends=True):
        out.write(line)
        out.flush()
    err = path.with_suffix(".stderr")
    if err.is_file():
        sys.stderr.buffer.write(err.read_bytes())
        sys.stderr.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())

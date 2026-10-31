# SPDX-License-Identifier: GPL-3.0-or-later
"""The night driver's loop (AGT-01..AGT-04, AGT-06; D-05, D-07, D-08, D-17, D-21, D-23..D-25,
D-34, D-48).

`drive(config, deps)` takes the picks one by one and gives each function at most
`attempts_per_function` counted sessions per pass (D-07), each a fresh `claude -p` session
(session.py) in the checkout root (F11). A function that used them all goes to the persisted
difficult list (build/driver/difficult.json) and comes back only through `deps.requeue`
(picker.requeue). The night ends at `max_sessions` launched sessions (every launch spends a
slot of the night cap, a transient one included: 07-26 fix round 1) or `target_matched`
matches (D-48), whichever comes first.

After each session, in this order:

1. the containers whose name has the attempt's prefix are removed (attempt.container_prefix);
2. the audit (D-17, F3; D-24 since 07-13): (a) every path `git status --porcelain=v1
   --untracked-files=all` lists after the session must hold, unstaged, the bytes the driver
   itself last wrote to it (the ledger: attempts.jsonl, status.csv, the feed), so every other
   path git can see equals HEAD; (b) every file of the session's private view but its unit and
   view/build/ is as it was at launch; every path a write tool names in the transcript must
   pass hooks.matching_write_allowed in view mode (the view unit, notes.md, proposals.jsonl);
   a fixed list of paths git cannot see (.git/config, .git/info/exclude
   and attributes, .git/hooks/, .githooks/, the two Claude settings files, the venv's
   pyvenv.cfg, .pth and *customize.py files) must keep their bytes; and the fingerprint (path,
   size, mtime_ns) of all of .venv, of every gitignored tree under .claude/ but
   .claude/worktrees/, and of every repo __pycache__ must not change
   (security rulings). A stray path stops the night (STOPPED `guardrail`) with nothing
   committed: each stray file is copied or moved into build/driver/<run>/quarantine/ (created
   at run start; no link followed, O_EXCL, never overwritten) and put back as it was, the
   attempt is reset, the snapshot is taken again, and the record lists every path. A session
   that raises is contained the same way before its ERROR stop. build/ itself is not audited:
   the attempt wrapper writes there by design (a known limit);
3. streamjson.classify (D-08): STOP stops the night; a check_init problem stops it too; LIMIT
   keeps the session's work (the gate runs on it as usual), then backs off 60, 120, 240 s and
   polls every 300 s, not counted; TRANSIENT resets and relaunches, and after the first launch
   and 3 retries (D-08) writes an `abort` record, not counted, though each transient launch
   spends a slot of the night cap (07-26 fix round 1); ATTEMPT_DONE (a result or a
   wall-clock timeout) is
   counted;
4. a counted session: the landing section copies the view unit into src/<exe>/<unit>.c (the
   only writer of src/), then the C89 lint of the unit, then the container gate. Only gate
   exit 0 is a match (D-24): never the transcript, the result event or /goal's verdict. A match
   is one commit with explicit paths only (D-25). Otherwise the landed unit alone is put back
   (D-34: HEAD's bytes, or deleted when HEAD has none) and the attempt is logged
   PARTIAL (best plain check above 0%, its C saved under best/ and `gate --partial` run) or
   GAVE_UP; a failed lint is the same outcome with abort_reason "lint" (review IN-02).

Claims and locks (07-18; D-06, D-24, D-27 P4): the drive verb (night, dry run or canary)
holds build/driver/drive.lock (an OS lock, locks.ProcessLock) from before its preflight to its
end and hands it to the night, so a second drive runs nothing and every earlier holder is
known dead; drive() alone takes its own. With it held, each claim of another run under
build/driver/claims/ is stale and moved to build/driver/<run>/stale-claims/, named in STARTED.
Each attempt claims its unit with one O_EXCL file and releases it after its landing decision.
One gate lock serialises every shared write (the landing section, `gate --partial`, every
record append) and one git lock every driver git call; git and sessions run with
GIT_OPTIONAL_LOCKS=0, and `git add`/`git commit` retry once on an index.lock error.

Workers (07-21; D-06, D-07): the coordinator (the main thread, `_Coordinator`) owns the picker
and hands each function's pass to one of `workers` worker threads (`_Worker`); a pick whose
unit another pass holds is skipped for now and handed out later, never dropped. One worker runs
on the calling thread, exactly the Phase 6 loop. Sessions run at once; the pre-session snapshot,
the audit and every landing hold the gate lock, so a gate sees src/ equal to HEAD but the unit
it lands. A LIMIT session pauses every worker (`_Pause`: one backoff, then exactly one probe
launch). Any worker's stop (or an interrupt on the main thread) stops them all: every live
session tree in the pid registry (run_session's on_start/on_end) is killed, each attempt is
contained and reset uncounted, and the first stop writes the one STOPPED record.

Records (07-23; DEC-06, DEC-07, D-08): the driver writes only schema-2 records. An attempt
carries its session kind, pass, worker, requested model and budget, hook blocks (the result
event's permission_denials), the gate's verdict and the sweep evidence; `function` is the
pick's C name. Each usage-limit wait is a `limit` record; STARTED names the workers and the
recovered claims, and ENDED/STOPPED carry the totals summed over the night's own records. A
function's pass is one more than its finished passes in the committed log (`pass_index`), read
once per night; build/driver/difficult.json stays a cache for the Phase 6 picker only.

Tiers (07-26; DEC-02, D-04, D-08, D-22, D-23): once config/mechanics.toml has a signed tier
whose digest still matches, `real_deps` queues picker.tier_queue instead of the pools: the
signed tiers' members callees first, then their hubs, never an asm row. The coordinator asks it
for the best eligible pick each time a worker is free; a capped function goes back for its next
pass the same night (night.passes counts it, and is the pass index the queue reads, so the
queue never reads difficult.json). The dry run and the night's draft picks are the tier
queue's first picks (`tier_picks`), the dry run's with their tier, level and pass.

Naming proposals (07-34; D-19, D-29): the driver is the only writer of naming state. After a
readability session (DriveConfig.session; ruling F34: never after a matching one) and before
its landing, `_apply_proposals` reads the session's proposals.jsonl and applies each proposal
in file order under the gate lock, against the naming state of that moment: a rename writes
symbols.csv (the new linker name) and rewrites the exact old C name in every committed user
in src/ and in the driver-written headers, a header proposal writes include/<name>.h; one
container gate (`Deps.rename_gate`) runs over every affected unit and includer, all or
nothing, and a pass is one `refactor(...)` commit with `Renamed-By: reverseapoc drive`, a
failure a byte-for-byte restore. Every proposal is a v2 `rename` record (APPLIED, DEFERRED,
REFUSED; ruling F12's shapes); a bad line is REFUSED, never a night stop. A proposal whose
affected unit another live session holds is DEFERRED and tried again after each claim
release (`_retry_deferred`); the proposing session's own unit never blocks, its view unit is
rewritten in place. At every landing the view unit first takes every rename committed since
the view's HEAD (`_renames_since`), so a session that started before a rename still lands.

Every effect is an injected dependency (`Deps`), so the tests run the stand-in claude
(tests/fakeclaude.py), fake gates and a tmp git repo. The `drive` verb (plan 06-25, at the end of
this module) wires the real ones (`real_deps`) behind a fail-closed `preflight`, and adds the
dry run, the owner-run canary and the end-of-run checks (`finish`). Every git call goes through
`--literal-pathspecs`, so no path is a glob.

Layout of one session (gitignored): build/driver/<run>/<exe>/<func>/attempt-<n>/ holds
transcript.jsonl, context.md, notes.md, proposals.jsonl, the wrapper's checks/ and
checks.jsonl, best/, view-head.txt (the commit the view came from, F34) and view/, the
session's private copy of HEAD's src/, include/ and config/ (D-24; its unit is the only file
the session edits, its build/ the wrapper's output). A
launch that did not count (LIMIT, TRANSIENT) is moved aside to attempt-<n>-uncounted-<k>, so
each session starts in a fresh directory.
"""

from __future__ import annotations

import csv
import functools
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import threading
import time
from collections.abc import Callable, Container, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from . import attempt, callgraph, hooks, mechanics, streamjson, unitdefs
from .callgraph import CallGraph
from .check import PERFECT, ExeInputs
from .contextpack import PACK_FILE, CallIndex, write_pack
from .fileio import write_atomic
from .functions import (
    KIND_GAME,
    KIND_RUNTIME,
    KIND_THUNK,
    SymbolRow,
    data_name,
    format_symbols_csv,
    game_name,
    read_functions_csv,
    read_symbols_csv,
    write_symbols_csv,
)
from .libmatch import read_runtime_csv, runtime_csv_path
from .locks import DRIVE_LOCK, ProcessLock
from .picker import EXE_ORDER, PILOT_PER_EXE, Key, Pick, TierItem, TierQueue, tier_queue
from .picker import pilot as picker_pilot
from .picker import queue as picker_queue
from .picker import requeue as picker_requeue
from .probe import CHK_PUBLIC
from .proposals import (
    RESERVED_HEADERS,
    Header,
    ProposalError,
    Rename,
    header_problem,
    linker_name,
    name_problem,
    parse_line,
    parse_proposals,
    read_bounded,
    rename_problem,
)
from .readlint import ReadlintError, run_readlint
from .score import Assessment, Candidate, assess, candidates, score, score_reasons
from .session import (
    FABLE_BUDGET_USD,
    FABLE_MODEL,
    MAX_BUDGET_USD,
    MAX_TURNS,
    MODEL,
    MODEL_NAMES,
    OPUS_MODEL,
    READABILITY_SKILL,
    TIMEOUT_S,
    SessionResult,
    build_argv,
    goal_prompt,
    kill_tree,
    model_for_pass,
    readability_goal,
    run_session,
)
from .status import MATCHED as STATUS_MATCHED
from .status import PARTIAL as STATUS_PARTIAL
from .status import read_status, status_path
from .streamjson import Disposition
from .units import scaffold_unit, write_unit_source

ATTEMPT_LOG = attempt.ATTEMPT_LOG  # progress/attempts.jsonl, committed (D-23)
DRIVER_DIR = Path(*attempt.DRIVER_PARTS)  # build/driver
DIFFICULT = DRIVER_DIR / "difficult.json"
CLAIMS_DIR = DRIVER_DIR / "claims"  # D-06: build/driver/claims/<exe>__<unit>.json, one per unit
STALE_CLAIMS = "stale-claims"  # build/driver/<run>/stale-claims/: claims of dead runs (D-06)
CLAIM_KEYS = ("run", "worker", "exe", "unit", "function", "start", "kind", "pass", "model",
              "claimed_at")  # fmt: skip
FEED = "decomphub.progress.json"  # gate-written, committed with status.csv
TRANSCRIPT = "transcript.jsonl"
COMMIT_MSG = "commit-msg.txt"
LOG_MSG = "commit-log.txt"  # under build/driver/<run>/
LOG_SUBJECT = "chore(driver): attempt log"  # D-23
BEST_DIR = "best"
VIEW_HEAD = "view-head.txt"  # <attempt dir>/view-head.txt: the commit the view came from (F34)
VIEW_TREES = ("src", "include", "config")  # D-24: what a view holds of HEAD
MATCHING_KIND = hooks.SESSION_KINDS[0]  # "matching" (D-18)
MATCHED_BY = "Matched-By: reverseapoc drive"
READABILITY_BY = "Readability-By: reverseapoc drive"  # 07-38: the trailer of a readability commit
LITERAL = "--literal-pathspecs"  # security ruling (06-23 commit_match): paths are never globs
OPTIONAL_LOCKS = "GIT_OPTIONAL_LOCKS"  # "0" in the driver's git env and every session's (D-27 P4)
INDEX_LOCK = b"index.lock"  # in git's stderr: another process held the index (D-27 P4)
INDEX_LOCK_WAIT_S = 1.0  # the wait before the one retry of `git add` / `git commit`
BACKOFF_S = (60, 120, 240)  # D-08: 1, 2 and 4 minutes
POLL_S = 300  # D-08: then every 5 minutes
TRANSIENT_RETRIES = 3  # D-08: "3 retries, then the attempt is aborted": 1 launch + 3 retries
EXIT_OK, EXIT_MISMATCH, EXIT_TOOL = 0, 1, 2
TESTED_MAJOR = 2  # D-36: the Claude CLI major the driver was tested with
MIN_CLI_VERSION = (2, 1, 302)  # D-36, research "Pilot checkpoint preflight": the -p default

MATCHED, PARTIAL, GAVE_UP = "MATCHED", "PARTIAL", "GAVE_UP"
CAPPED = "capped"  # a pass that used every attempt without a match (never a record outcome)
ABORTED = "aborted"  # an attempt a transient abort ended (an abort record; no attempt outcome)
KIND_ATTEMPT, KIND_ABORT, KIND_RUN = "attempt", "abort", "run"
STARTED, STOPPED, ENDED = "STARTED", "STOPPED", "ENDED"
REFUSED = "REFUSED"  # a report only: the night did not start, so no run record is written
START = "start"
NOTHING_TO_DO, MAX_SESSIONS, TARGET_MATCHED, QUEUE_EXHAUSTED = (
    "nothing to do", "max sessions", "target matched", "queue exhausted")  # fmt: skip
GUARDRAIL, STOP_SIGNAL, INIT, ERROR, TOOL = "guardrail", "stop signal", "init", "error", "tool"
INTERRUPTED = "interrupted"  # KeyboardInterrupt/SystemExit: recorded, then re-raised
LINT, TIMEOUT = "lint", "timeout"  # an attempt record's abort_reason
TRANSIENT = "transient"  # an abort record's abort_reason

_RUN_ID = re.compile(r"[A-Za-z0-9_.-]+")
_SHA1 = re.compile(r"[0-9a-f]{40}")
_HEADER = re.compile(r"include/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*\.h")  # security ruling
_SOURCE = re.compile(r"checks/[0-9]{4}\.c")  # attempt.CheckLogLine.source
_LONG_HEX = re.compile(r"[0-9A-Fa-f]{65,}")
_DETAIL_CAP = 4000  # a guardrail record lists every stray, restored and quarantined path
_TEXT_CAP = 200
_TRANSCRIPT_MARK = " (transcript)"
QUARANTINE = "quarantine"  # build/driver/<run>/quarantine/: a breach's files, never deleted
_GIT_PREFIX = ".git/"  # a pinned name under the common git directory
_PINNED_FILES = (".claude/settings.local.json", "config/driver/claude-settings.json",
                 ".venv/pyvenv.cfg")  # fmt: skip
_PTH_GLOBS = (".venv/Lib/site-packages/*.pth", ".venv/lib/python*/site-packages/*.pth")
_SITE_GLOBS = (".venv/Lib/site-packages", ".venv/lib/python*/site-packages")
_GIT_PINNED = ("config", "info/exclude", "info/attributes")  # under the common git directory
_CUSTOMIZE = ("sitecustomize.py", "usercustomize.py")  # anywhere under the venv
_VENV = ".venv"
_NOT_FINGERPRINTED = ("build", _VENV, ".git")  # top-level directories the __pycache__ scan skips
_PYCACHE = "__pycache__"
_CLAUDE = ".claude"
_WORKTREES = ".claude/worktrees"  # other agents' checkouts: never fingerprinted
_LISTED_CAP = 50  # paths named in one STOPPED record list before "and N more"
_O_NEW = (os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
          | getattr(os, "O_BINARY", 0))  # fmt: skip


class DriverError(RuntimeError):
    """A driver step failed in a way no session caused (git, the gate's output, a driver file)."""


def coauthor(model: str) -> str:
    """D-25 (07-30, D-09): the Co-Authored-By line of a commit `model` wrote, its display name
    from session.MODEL_NAMES (07-42); a model the table does not name raises DriverError, so a
    commit is never mislabelled (T-07-89)."""
    name = MODEL_NAMES.get(model)
    if name is None:
        raise DriverError(f"model {model!r} has no co-author name in session.MODEL_NAMES; "
                          "nothing is committed under an unknown model")  # fmt: skip
    return f"Co-Authored-By: {name} <noreply@anthropic.com>"


COAUTHOR = coauthor(OPUS_MODEL)  # D-25: the Opus line (passes 1 and 2), set explicitly


@dataclass(frozen=True)
class DriveConfig:
    """One night. `max_sessions` caps the sessions launched across every worker, aborted and
    counted ones alike (D-07, D-08, D-48; 07-26 fix round 1: a transient launch spends its slot,
    a LIMIT relaunch keeps it); `target_matched` 0 is off (the night cap governs; AGT-11 is
    counted by `stats`). 07-30: the per-model session budgets (D-07, D-25) and max_turns."""

    run_id: str
    repo_root: Path
    tested_major: int  # F28; plan 06-25 passes session's TESTED_MAJOR
    min_cli_version: tuple[int, int, int]  # F28; plan 06-25 passes MIN_CLI_VERSION
    max_sessions: int = 60  # D-07 (it was 30, D-48)
    target_matched: int = 0  # D-07 CONTEXT default: off (it was 10, D-48)
    attempts_per_function: int = 3  # D-07, per pass
    wall_clock_s: float = TIMEOUT_S  # D-07
    base_env: Mapping[str, str] | None = None  # the sessions' environment; None: os.environ
    workers: int = 1  # D-06: sessions at once; 1 is the Phase 6 serial driver (the verb: 3)
    max_budget_usd: float = MAX_BUDGET_USD  # D-07: per Opus session (07-30: a drive flag)
    fable_budget_usd: float = FABLE_BUDGET_USD  # D-25: per Fable session
    max_turns: int = MAX_TURNS  # D-07
    # 07-34 (D-18, ruling F34): the night's session kind. Only a readability session's
    # proposals.jsonl is applied (D-19), so matching nights keep the placeholders (D-17).
    session: str = MATCHING_KIND

    def budget_for(self, model: str) -> float:
        """The per-session budget of `model` (D-07, D-25): Fable's for FABLE_MODEL, else Opus's."""
        return session_budget(model, self.max_budget_usd, self.fable_budget_usd)


@dataclass(frozen=True)
class PackInfo:
    """What `reverseapoc context --json` reports for attempts.jsonl (D-14)."""

    pack_bytes: int
    truncated: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateRun:
    """`gate EXE/UNIT --attempts N --json` in the container: its exit code and parsed JSON.
    `matched_before` (07-23) is set by the driver: the claimed unit's matched starts in
    status.csv right before the gate ran, so the record can count regressions."""

    exit_code: int
    doc: Mapping | None = None
    matched_before: frozenset[int] = frozenset()


def session_budget(model: str, max_budget_usd: float, fable_budget_usd: float) -> float:
    """07-30 (D-07, D-25): a session's --max-budget-usd, picked by its requested model."""
    return fable_budget_usd if model == FABLE_MODEL else max_budget_usd


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _quiet(text: str) -> None:
    """The silent console: --json mode, and every Deps or finish no verb wired (261026-9ue)."""


@dataclass(frozen=True)
class Deps:
    """Every effect of the loop (D-05). `queue(difficult)` yields the picks, skipping the
    difficult keys, or is a picker.TierQueue (07-26), which the coordinator asks for its next
    eligible pick each time a worker is free; `requeue(difficult)` is picker.requeue wired
    with the matched set, callees and pool state; `matched_callees(pick)` is the snapshot kept
    with a capped function;
    `scaffold(pick, dest)` writes the unit's scaffold from the committed CSVs to `dest` (the
    view unit, 07-13); `pack(pick, dir, src)` builds the context pack into the attempt dir from
    the src tree `src` (the view's, 07-13); `argv(prompt, *, model, max_budget_usd, max_turns)`
    is the claude argv of one session (session.build_argv; 07-30: the pass's model and budget,
    D-09, D-25); `session` is session.run_session; `lint(pick)` is the C89 lint of the
    unit (0/1/2); `gate(pick, n)` and `partial_gate(pick, src, n)` are the container gates;
    `remove_containers(prefix)` removes containers by name prefix; `git(args)` runs git in the
    checkout. `say(text)` names one progress line: an attempt's start, a usage-limit wait or
    the attempt's outcome; the drive verb wires `console`, which stamps it and stays silent in
    --json; the default prints nothing (quick 261026-9ue). `kill(pid)` kills a live session's
    whole tree (session.kill_tree) when the night stops (07-21 stop-all)."""

    queue: Callable[[Container[Key]], Iterable[Pick] | TierQueue]
    requeue: Callable[[Mapping[Key, tuple[Key, ...]]], Iterable[Key]]
    matched_callees: Callable[[Pick], tuple[Key, ...]]
    scaffold: Callable[[Pick, Path], None]
    pack: Callable[[Pick, Path, Path], PackInfo]
    argv: Callable[..., Sequence[str]]  # (prompt, *, model, max_budget_usd, max_turns)
    session: Callable[..., SessionResult]
    lint: Callable[[Pick], int]
    gate: Callable[[Pick, int], GateRun]
    partial_gate: Callable[[Pick, str, int], int]
    remove_containers: Callable[[str], None]
    git: Callable[..., subprocess.CompletedProcess]  # (args), or (args, input=bytes): stdin
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    today: Callable[[], str] = _today
    # Fix round 4 L1: the end-of-run checks (06-25 wires ninja verify and gate --all); each
    # failed check is one string. Called after the last session, before the ENDED record.
    end_of_run: Callable[[], Sequence[str]] = tuple
    say: Callable[[str], None] = _quiet
    kill: Callable[[int], None] = kill_tree  # 07-21 stop-all: a live session's whole tree
    # 07-34 (D-19): one container gate over the affected units of a rename or header proposal
    # (`gate u1 u2 ... --json`, all or nothing), and the LE data objects of an EXE (a data
    # rename must lie in one; none: every data rename is refused, fail closed).
    rename_gate: Callable[[Sequence[str]], GateRun] = lambda targets: GateRun(EXIT_TOOL)
    data_ranges: Callable[[str], Sequence[tuple[int, int]]] = lambda exe: ()


@dataclass(frozen=True)
class DriveReport:
    """How the night ended: ENDED or STOPPED, why, and its counts."""

    event: str
    reason: str
    sessions: int
    matched: int
    detail: str | None = None
    checks_failed: tuple[str, ...] = ()  # the end-of-run checks that failed (L1)

    @property
    def exit_code(self) -> int:
        """0 ENDED with every end-of-run check passing, 2 REFUSED (the night never started),
        1 otherwise (STOPPED, or ENDED with a failed check, fix round 4 L1)."""
        if self.event == ENDED:
            return 1 if self.checks_failed else 0
        return 2 if self.event == REFUSED else 1


def git_runner(repo: Path, *, env: Mapping[str, str] | None = None):
    """`git <args>` in `repo` as an argv list, never a shell; stdout and stderr as bytes. The
    env (given, else this process's) carries GIT_OPTIONAL_LOCKS=0, so a read such as `git
    status` never takes index.lock (D-27 P4). `input`, when given, is git's stdin (07-21 fix
    round 2: `hash-object --stdin`)."""
    run_env = {**(os.environ if env is None else env), OPTIONAL_LOCKS: "0"}

    def git(args: Sequence[str], input: bytes | None = None) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(["git", *args], cwd=repo, env=dict(run_env), input=input,
                                  capture_output=True, check=False)  # fmt: skip
        except OSError as exc:  # fix round 1 I2: a missing or unrunnable git is a failed call
            return subprocess.CompletedProcess(["git", *args], _os_error_exit(exc), b"",
                                               f"git: {exc}".encode("utf-8", "replace"))

    return git


def _os_error_exit(exc: OSError) -> int:
    """127 for a program that is not there, 126 for any other reason it could not run (the
    shell's convention)."""
    return 127 if isinstance(exc, FileNotFoundError) else 126


def _git_ok(git: Callable[[Sequence[str]], subprocess.CompletedProcess], args: list[str]) -> bytes:
    """`git --literal-pathspecs <args>`; a non-zero exit is a DriverError."""
    return _git_stdout(git([LITERAL, *args]), args)


def _git_stdout(done: subprocess.CompletedProcess, args: Sequence[str]) -> bytes:
    """The stdout of a finished `git <args>`; a non-zero exit is a DriverError naming git's
    stderr."""
    if done.returncode != 0:
        why = (done.stderr or b"").decode("utf-8", "replace").strip()
        raise DriverError(f"git {' '.join(args[:2])} failed: {why}")
    return done.stdout or b""


def _detail(text: str) -> str:
    """A message fit for a record: long hex runs masked, capped in length."""
    return _LONG_HEX.sub("<hex>", text)[:_DETAIL_CAP]


# ---- the attempt log ----


class RecordError(ValueError):
    """A record that does not follow the attempts.jsonl schema (D-23)."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_number(value: object) -> bool:
    return _number(value) and value >= 0


def _matches(pattern: re.Pattern) -> Callable[[object], bool]:
    return lambda value: isinstance(value, str) and pattern.fullmatch(value) is not None


def _one_of(*values: object) -> Callable[[object], bool]:
    return lambda value: value in values and (value is None or isinstance(value, str))


def _optional(check: Callable[[object], bool]) -> Callable[[object], bool]:
    return lambda value: value is None or check(value)


def _is_text(value: object) -> bool:
    return isinstance(value, str)


def _shaped(fields: Mapping[str, Callable[[object], bool]]) -> Callable[[object], bool]:
    def check(value: object) -> bool:
        return (isinstance(value, dict) and set(value) == set(fields)
                and all(ok(value[key]) for key, ok in fields.items()))  # fmt: skip

    return check


def _strings_list(value: object) -> bool:
    return isinstance(value, list) and all(map(_is_text, value))


_COUNT_KEYS = ("input", "output", "cache_read", "cache_creation")
_CLAIM_FIELDS = {
    "run": _matches(_RUN_ID),
    "exe": _one_of("ufo2p", "tacp"),
    "function": _matches(re.compile(r"func_[0-9A-F]{8}")),
    "unit": _matches(re.compile(r"[a-z0-9_]+")),
    "start": _matches(re.compile(r"0x[0-9A-F]{8}")),
    "attempt": lambda value: _is_int(value) and value >= 1,
    "date": _matches(re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")),
}
RECORD_FIELDS: dict[str, dict[str, Callable[[object], bool]]] = {
    KIND_ATTEMPT: {
        **_CLAIM_FIELDS,
        "kind": _one_of(KIND_ATTEMPT),
        "outcome": _one_of(MATCHED, PARTIAL, GAVE_UP),
        "abort_reason": _one_of(None, LINT, TIMEOUT, GUARDRAIL, TOOL),
        "turns": _is_int,
        "tokens": _shaped(dict.fromkeys(_COUNT_KEYS, _is_int)),
        "cost_usd": _is_number,
        "seconds": _is_number,
        "model": _optional(_is_text),
        "cli_version": _optional(_is_text),
        "check": _shaped(
            {
                "runs": _is_int,
                "best_percent": _optional(_is_number),
                "sweep_hit": _optional(_is_text),
                "needs": _optional(_is_text),
            }
        ),
        "pack_bytes": _is_int,
        "truncated": lambda value: isinstance(value, list) and all(map(_is_text, value)),
    },  # fmt: skip
    KIND_ABORT: {
        **_CLAIM_FIELDS,
        "kind": _one_of(KIND_ABORT),
        "abort_reason": _one_of(TRANSIENT),
        "retries": _is_int,
    },
    KIND_RUN: {
        "kind": _one_of(KIND_RUN),
        "run": _matches(_RUN_ID),
        "event": _one_of(STARTED, STOPPED, ENDED),
        "reason": _is_text,  # checked against the event below (F30)
        "detail": _optional(_is_text),
        "sessions": _is_int,
        "matched": _is_int,
        "checks_failed": _strings_list,  # fix round 4 L1: the end-of-run checks that failed
        "uncommitted": _strings_list,  # L2: partial rows a STOPPED night leaves uncommitted
        "date": _CLAIM_FIELDS["date"],
    },
}
RUN_REASONS = {
    STARTED: (START,),
    STOPPED: (GUARDRAIL, STOP_SIGNAL, INIT, ERROR, TOOL, INTERRUPTED),
    ENDED: (NOTHING_TO_DO, MAX_SESSIONS, TARGET_MATCHED, QUEUE_EXHAUSTED),
}

# Schema 2 (Phase 7, DEC-06/DEC-07, research section J): a v2 line carries "schema": 2 and
# validates against RECORD_FIELDS_V2; a line without "schema" is v1 and validates against
# RECORD_FIELDS unchanged, so the committed v1 history stays valid (D-23: never rewritten).
SCHEMA_V2 = 2
MATCHING, READABILITY = "matching", "readability"
SESSIONS = (MATCHING, READABILITY)  # D-18: two session kinds, kept apart by stats
LANDED = "LANDED"  # a readability session's unit landed; REFUSED (above) is its refusal
SESSION_OUTCOMES = {
    MATCHING: (MATCHED, PARTIAL, GAVE_UP),
    READABILITY: (LANDED, PARTIAL, REFUSED, GAVE_UP),
}
_V2_OUTCOMES = tuple(dict.fromkeys(SESSION_OUTCOMES[MATCHING] + SESSION_OUTCOMES[READABILITY]))
_C_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")  # v2: a renamed function keeps its C name (D-19)


def _is_bool(value: object) -> bool:
    return isinstance(value, bool)


def _is_positive_number(value: object) -> bool:
    return _number(value) and value > 0


_GATE = _optional(_shaped({
    "exit": _optional(_is_int),
    "claimed_ok": _is_bool,
    "regressions": _is_int,
    "problems": _strings_list,
}))  # fmt: skip
_SCHEMA_V2_FIELD = {"schema": lambda value: type(value) is int and value == SCHEMA_V2}
_V2_SESSION_FIELDS = {
    **_SCHEMA_V2_FIELD,
    "session": _one_of(*SESSIONS),
    "pass": lambda value: _is_int(value) and value >= 1,
    "worker": _is_int,
}
KIND_LIMIT = "limit"  # a usage-limit wait (D-07: it pauses every worker)
KIND_RENAME = "rename"  # one applied, deferred or refused naming proposal (D-19)
APPLIED, DEFERRED = "APPLIED", "DEFERRED"
RENAME_OUTCOMES = (APPLIED, DEFERRED, REFUSED)
OP_RENAME, OP_HEADER = "rename", "header"  # research section 6: the proposal ops
# Orchestrator ruling F12: the keys each op fills; every other one of them is null. A line
# the driver could not parse has op null and is always REFUSED.
_RENAME_NAMED = ("exe", "address", "old", "new")
_RENAME_OP_KEYS = {OP_RENAME: frozenset(_RENAME_NAMED), OP_HEADER: frozenset({"path"}),
                   None: frozenset()}  # fmt: skip


def _mapping_of(
    key_ok: Callable[[object], bool], value_ok: Callable[[object], bool]
) -> Callable[[object], bool]:
    return lambda value: isinstance(value, dict) and all(
        key_ok(key) and value_ok(item) for key, item in value.items())  # fmt: skip


def _list_of(item_ok: Callable[[object], bool]) -> Callable[[object], bool]:
    return lambda value: isinstance(value, list) and all(map(item_ok, value))


def _at_least_one(value: object) -> bool:
    return _is_int(value) and value >= 1


_SHARE = _shaped({"sessions": _is_int, "matched": _is_int, "cost_usd": _is_number})
_TOTALS = _shaped({
    "sessions": _shaped(dict.fromkeys(_V2_OUTCOMES, _is_int)),  # counted sessions by outcome
    "turns": _is_int,
    "tokens": _shaped(dict.fromkeys(_COUNT_KEYS, _is_int)),
    "cost_usd": _is_number,
    "session_seconds": _is_number,  # the sum over sessions
    "wall_seconds": _is_number,  # the night's wall clock
    "hook_blocks": _is_int,
    "regressions_stopped": _is_int,
    "limit_waits": _shaped({"count": _is_int, "seconds": _is_number}),
    "aborts": _is_int,
    "by_model": _mapping_of(_is_text, _SHARE),
    "by_session": _mapping_of(_one_of(*SESSIONS), _SHARE),
})  # fmt: skip
_RECOVERED = _shaped({key: _CLAIM_FIELDS[key] for key in ("exe", "unit", "run")})
RECORD_FIELDS_V2: dict[str, dict[str, Callable[[object], bool]]] = {
    KIND_ABORT: {
        **RECORD_FIELDS[KIND_ABORT],
        **_V2_SESSION_FIELDS,
        "function": _matches(_C_NAME),  # F12: the same C-name rule as a v2 attempt
    },
    KIND_RUN: {
        **RECORD_FIELDS[KIND_RUN],
        **_SCHEMA_V2_FIELD,
        "workers": _at_least_one,
        "recovered": _list_of(_RECOVERED),  # stale claims recovered at STARTED
        "totals": _optional(_TOTALS),  # null on STARTED only (_run_problem)
    },
    KIND_LIMIT: {
        "kind": _one_of(KIND_LIMIT),
        **_SCHEMA_V2_FIELD,
        "run": _CLAIM_FIELDS["run"],
        "worker": _is_int,
        "seconds": _is_number,
        "streak": _at_least_one,
        "date": _CLAIM_FIELDS["date"],
    },
    KIND_RENAME: {
        "kind": _one_of(KIND_RENAME),
        **_SCHEMA_V2_FIELD,
        "run": _CLAIM_FIELDS["run"],
        "exe": _optional(_CLAIM_FIELDS["exe"]),
        "address": _optional(_CLAIM_FIELDS["start"]),
        "old": _optional(_matches(_C_NAME)),
        "new": _optional(_matches(_C_NAME)),
        "op": _one_of(None, *_RENAME_OP_KEYS),
        "path": _optional(_matches(_HEADER)),
        "outcome": _one_of(*RENAME_OUTCOMES),
        "reason": _optional(_is_text),
        "commit": _optional(_matches(_SHA1)),  # the APPLIED commit only
        "date": _CLAIM_FIELDS["date"],
    },
    KIND_ATTEMPT: {
        **RECORD_FIELDS[KIND_ATTEMPT],
        **_V2_SESSION_FIELDS,
        "function": _matches(_C_NAME),
        "outcome": _one_of(*_V2_OUTCOMES),  # and one of its session's (_kind_problem)
        "model_requested": _is_text,
        "budget_usd": _is_positive_number,
        "hook_blocks": _is_int,
        "gate": _GATE,
        "sweep_source": _optional(_matches(_SOURCE)),
        "sweep_cells_100": _strings_list,
    },  # fmt: skip
}


def _strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _record_fields(obj: dict) -> dict[str, Callable[[object], bool]]:
    """The field table of `obj`'s schema and kind: no `schema` key is v1, `"schema": 2` (an
    int, not a bool or a float) is v2, anything else is a RecordError."""
    if "schema" not in obj:
        table = RECORD_FIELDS
    elif _SCHEMA_V2_FIELD["schema"](obj["schema"]):
        table = RECORD_FIELDS_V2
    else:
        raise RecordError(f"unknown schema {obj['schema']!r}")
    kind = obj.get("kind")
    fields = table.get(kind) if isinstance(kind, str) else None
    if fields is None:
        version = "v1" if table is RECORD_FIELDS else "v2"
        raise RecordError(f"unknown {version} record kind {kind!r}")
    return fields


def _run_problem(obj: dict) -> str | None:
    """A reason of the record's event (F30); a v2 record's totals null exactly on STARTED."""
    if obj["reason"] not in RUN_REASONS[obj["event"]]:
        return f"run record: {obj['reason']!r} is no reason for {obj['event']}"
    if "schema" not in obj or (obj["totals"] is None) == (obj["event"] == STARTED):
        return None
    if obj["event"] == STARTED:
        return "run record: a STARTED record takes no totals"
    return f"run record: a {obj['event']} record needs its totals"


def _rename_problem(obj: dict) -> str | None:
    """F12's per-op shapes: the op's keys filled and the others null, an unparseable line
    (op null) only REFUSED, a commit exactly when APPLIED, a reason when not APPLIED."""
    filled = {key for key in (*_RENAME_NAMED, "path") if obj[key] is not None}
    wanted = _RENAME_OP_KEYS[obj["op"]]
    if filled != wanted:
        return f"rename record: op {obj['op']!r} fills {sorted(wanted)}, not {sorted(filled)}"
    if obj["op"] is None and obj["outcome"] != REFUSED:
        return "rename record: a line the driver could not parse is REFUSED"
    if obj["outcome"] == APPLIED and obj["commit"] is None:
        return "rename record: an APPLIED rename names its commit"
    if obj["outcome"] != APPLIED and obj["commit"] is not None:
        return f"rename record: a {obj['outcome']} rename has no commit"
    if obj["outcome"] != APPLIED and obj["reason"] is None:
        return f"rename record: {obj['outcome']} names its reason"
    return None


def _kind_problem(obj: dict) -> str | None:
    """The rule a record's key set and value types cannot state, or None."""
    if obj["kind"] == KIND_RUN:
        return _run_problem(obj)
    if obj["kind"] == KIND_RENAME:
        return _rename_problem(obj)
    if "outcome" in obj and "session" in obj and obj["outcome"] not in SESSION_OUTCOMES[
            obj["session"]]:  # fmt: skip
        return f"{obj['kind']} record: {obj['outcome']!r} is no {obj['session']} outcome"
    return None


def validate_record(obj: object) -> None:
    """Raise RecordError unless `obj` is one attempts.jsonl record (D-23): the exact key set
    of its schema and kind (v1 `attempt`, `abort`, `run`; v2 lines carry `"schema": 2`), every
    value of the pinned type or enum, a run record's `reason` one of its event's (F30), a v2
    outcome one of its session's (D-18), and no string anywhere holding a hex run longer than
    64 characters (no game bytes, T-06-55)."""
    if not isinstance(obj, dict):
        raise RecordError(f"a record is a JSON object, not {type(obj).__name__}")
    fields = _record_fields(obj)
    missing, extra = sorted(set(fields) - set(obj)), sorted(set(obj) - set(fields))
    if missing or extra:
        raise RecordError(f"{obj['kind']} record: missing {missing}, extra {extra}")
    bad = [key for key, ok in fields.items() if not ok(obj[key])]
    if bad:
        raise RecordError(f"{obj['kind']} record: bad value for {', '.join(bad)}")
    problem = _kind_problem(obj)
    if problem:
        raise RecordError(problem)
    if any(_LONG_HEX.search(text) for text in _strings(obj)):
        raise RecordError(f"{obj['kind']} record holds a hex string longer than 64 characters")


def append_record(path: Path, record: Mapping) -> None:
    """Validate `record`, then append it as one compact JSON line (LF) to `path`; a record is
    never rewritten (D-23)."""
    line = record_line(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as fh:
        fh.write(line)


def record_line(record: Mapping) -> bytes:
    """`record` validated, as the one compact JSON line (LF, ASCII) append_record writes."""
    validate_record(record)
    return (json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


# ---- the commit (D-25) ----


def commit_message(
    *,
    exe: str,
    function: str,
    unit: str,
    attempt_n: int,
    attempts: int,
    model: str | None,
    usage: streamjson.Usage,
    seconds: float,
    sha1s: Sequence[tuple[str, str]],
    requested_model: str,
) -> str:
    """D-25's message for one match: subject, the attempt's figures, both SHA-1s, trailers.
    `model` is the init event's (the `model` line); `requested_model` the session's, which the
    init check has matched, and names the co-author (07-30: coauthor raises DriverError for a
    model it does not know, before anything is committed)."""
    trailer = coauthor(requested_model)
    lines = [
        f"feat({exe}): match {function} in {unit} (C89)",
        "",
        f"attempt {attempt_n}/{attempts}",
        f"model {model or 'unknown'}",
        f"turns {usage.turns}",
        f"tokens {usage.input_tokens} input, {usage.output_tokens} output, "
        f"{usage.cache_read_tokens} cache read, {usage.cache_creation_tokens} cache creation",
        f"seconds {round(seconds)}",
        "objdiff 100%",
        "relocation ok",
        *(f"sha1 {name} {sha1}" for name, sha1 in sha1s),
        "",
        trailer,
        MATCHED_BY,
    ]
    return "\n".join(lines) + "\n"


def readability_message(
    *,
    exe: str,
    unit: str,
    attempt_n: int,
    model: str | None,
    usage: streamjson.Usage,
    seconds: float,
    sha1s: Sequence[tuple[str, str]],
    requested_model: str,
) -> str:
    """07-38 (D-17): the message of one readability landing, one unit per commit: the subject,
    the session's figures, the gate's verdict (the bytes did not move) and both SHA-1s, then the
    requested model's co-author line (coauthor raises DriverError for an unknown model, before
    anything is committed) and READABILITY_BY."""
    lines = [
        f"refactor({exe}): name and document {unit} (readability)",
        "",
        f"attempt {attempt_n}",
        f"model {model or 'unknown'}",
        f"turns {usage.turns}",
        f"tokens {usage.input_tokens} input, {usage.output_tokens} output, "
        f"{usage.cache_read_tokens} cache read, {usage.cache_creation_tokens} cache creation",
        f"seconds {round(seconds)}",
        "gate ok: the unit's bytes are unchanged",
        "readlint clean",
        *(f"sha1 {name} {sha1}" for name, sha1 in sha1s),
        "",
        coauthor(requested_model),
        READABILITY_BY,
    ]
    return "\n".join(lines) + "\n"


_UNCLAIMED_PASS = "the gate passed without a matched row for the claimed function"


def claimed_matched(doc: Mapping | None, pick: Pick) -> bool:
    """06-REVIEW CR-01: True when a gate's JSON `written` (the status.csv rows it wrote, one per
    function of the unit that passed) holds a matched row for the claimed function, the same
    rule attempt._verdict applies to the claimed function of a check (D-24)."""
    want = f"0x{pick.start:08X}"
    written = doc.get("written") if isinstance(doc, Mapping) else None
    return isinstance(written, list) and any(
        isinstance(row, Mapping) and row.get("start") == want and row.get("unit") == pick.unit
        and row.get("status") == STATUS_MATCHED
        for row in written
    )  # fmt: skip


def _splice_lists(doc: Mapping | None) -> Iterator[object]:
    """The `splice` lists of a gate's JSON (gate.GateResult.to_json): each check's, which a
    per-unit gate fills, and the top-level one, which `gate --all` fills (07-34 fix round 1)."""
    if not isinstance(doc, Mapping):
        return
    checks = doc.get("checks")
    for check in checks if isinstance(checks, list) else ():
        if isinstance(check, Mapping):
            yield check.get("splice")
    yield doc.get("splice")


def gate_sha1s(doc: Mapping | None) -> list[tuple[str, str]]:
    """(EXE name, SHA-1) of each landed EXE in a gate's JSON: its checks' `splice` entries
    (per-unit gate) and its top-level `splice` entries (`gate --all`)."""
    found: dict[str, str] = {}
    for splices in _splice_lists(doc):
        for entry in splices if isinstance(splices, list) else ():
            if not isinstance(entry, Mapping):
                continue
            name, sha1 = entry.get("exe"), entry.get("sha1")
            if isinstance(name, str) and isinstance(sha1, str) and _SHA1.fullmatch(sha1):
                found.setdefault(name, sha1)
    return sorted(found.items())


# ---- the audit (D-17, F3) ----


def parse_status(raw: bytes) -> dict[str, str]:
    """`git status --porcelain=v1 -z` as {path: XY code}; a rename's or copy's source path is
    listed too, with the same code."""
    entries: dict[str, str] = {}
    fields = iter(raw.decode("utf-8", "surrogateescape").split("\0"))
    for entry in fields:
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        entries[path] = code
        if code[0] in "RC":
            source = next(fields, "")
            if source:
                entries[source] = code
    return entries


def _read(path: Path) -> bytes | None:
    """The bytes of a regular file, None when there is none (or the name cannot exist)."""
    try:
        return path.read_bytes() if path.is_file() else None
    except OSError, ValueError:
        return None


def _sha256(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


def _files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.rglob("*") if p.is_file()) if directory.is_dir() else []


def _walk(
    root: Path, *, skip_top: Sequence[str] = (), prune: Sequence[Path] = ()
) -> Iterable[tuple[Path, list[str]]]:
    """(directory, its file names) under `root`, never following a link, the top-level
    directories in `skip_top` and every directory in `prune` (at any depth) left out."""
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        if here == root:
            dirnames[:] = [d for d in dirnames if d not in skip_top]
        dirnames[:] = [d for d in dirnames if here / d not in prune]
        yield here, filenames


def _is_link(path: Path) -> bool:
    """A symlink, a junction or any other reparse point (never followed)."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    reparse = getattr(st, "st_file_attributes", 0) & getattr(
        stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0
    )
    return stat.S_ISLNK(st.st_mode) or bool(reparse) or os.path.isjunction(path)


def _write_new(target: Path, data: bytes) -> None:
    """Create `target` with O_CREAT|O_EXCL (and O_NOFOLLOW where it exists): never overwrites,
    never writes through a link."""
    fd = os.open(target, _O_NEW, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def _listed(names: Sequence[str]) -> str:
    """At most _LISTED_CAP names, then how many more."""
    shown = ", ".join(names[:_LISTED_CAP]) or "none"
    more = len(names) - _LISTED_CAP
    return f"{shown} (and {more} more)" if more > 0 else shown


def _write_targets(events: Sequence[dict]) -> list[str | None]:
    """The path of every write-tool call in the transcript (None when it names none)."""
    return [use.target for use in streamjson.tool_uses(events) if use.name in hooks.EDIT_TOOLS]


def _roots(repo: Path, cwd: object) -> list[str]:
    """The casefolded forms of the checkout root: the driver's path and the cwd the CLI reports
    in its init event (the same directory, possibly spelled another way)."""
    forms = list(hooks.candidates(str(repo)))
    if isinstance(cwd, str) and cwd:
        try:
            forms += hooks.candidates(cwd, str(repo))
        except hooks.HookError:
            pass
    return [form.casefold().rstrip("/") for form in forms]


def _below(folded: str, roots: Sequence[str]) -> str | None:
    for base in roots:
        if folded.startswith(base + "/"):
            return folded[len(base) + 1 :]
    return None


def _relative(raw: str | None, repo: Path, roots: Sequence[str]) -> list[str] | None:
    """Every repo-relative form of `raw` (casefolded), or None when a form is outside."""
    if raw is None:
        return None
    try:
        forms = hooks.candidates(raw, str(repo))
    except hooks.HookError:
        return None
    rels = [_below(form.casefold(), roots) for form in forms]
    return None if any(rel is None for rel in rels) else sorted(set(rels))


def transcript_paths(events: Sequence[dict], repo: Path) -> list[list[str] | None]:
    """For each write-tool call in the transcript, its repo-relative forms, or None when it
    names no path or one outside the checkout (judged against `repo` and the init cwd)."""
    roots = _roots(repo, (streamjson.init_event(events) or {}).get("cwd"))
    return [_relative(raw, repo, roots) for raw in _write_targets(events)]


# ---- checks.jsonl and the best C (F10) ----


@dataclass(frozen=True)
class CheckSummary:
    """The wrapper's checks.jsonl for one attempt: how many runs, the best plain percent and
    the C it checked, and the first sweep hit."""

    runs: int = 0
    best_percent: float | None = None
    best_source: str | None = None
    sweep_hit: str | None = None

    def to_json(self) -> dict:
        needs = f"needs flags {self.sweep_hit}" if self.sweep_hit else None
        return {"runs": self.runs, "best_percent": self.best_percent,
                "sweep_hit": self.sweep_hit, "needs": needs}  # fmt: skip


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _check_line(raw: str) -> dict | None:
    """One well-formed checks.jsonl line, or None."""
    try:
        line = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(line, dict):
        return None
    hit, percent, source = line.get("sweep_hit"), line.get("best_percent"), line.get("source")
    if not (_number(line.get("exit")) and isinstance(line.get("sweep"), bool)):
        return None
    if not (percent is None or _number(percent)) or not isinstance(source, str):
        return None
    if not _SOURCE.fullmatch(source) or not (hit is None or isinstance(hit, str)):
        return None
    return line


def _readable(line: Mapping) -> bool:
    """07-38 (the 07-31 review note): a readability check whose run passed with readlint clean:
    a plain line of exit 0 with `readlint_violations` 0 (null: readlint did not run)."""
    violations = line.get("readlint_violations")
    return (not line["sweep"] and line["exit"] == EXIT_OK and _number(violations)
            and violations == 0 and line["best_percent"] is not None)  # fmt: skip


def read_checks(attempt_dir: Path, *, readability: bool = False) -> CheckSummary:
    """F10: the best C is the line with the highest best_percent among plain lines (never a
    sweep, whose percent is under other flags), skipping null percents and exit-2 runs; ties
    go to the earliest. 07-38 (the 07-31 review note): in a readability session every run is
    100%, so `readability` picks the latest run whose readlint passed instead (none: no best).
    The readability landing lands the view unit itself, never this line's C."""
    path = Path(attempt_dir) / attempt.CHECK_LOG
    if not path.is_file():
        return CheckSummary()
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line for raw in text.splitlines() if (line := _check_line(raw)) is not None]
    best = None
    for line in lines:
        if readability:
            best = line if _readable(line) else best
            continue
        if line["sweep"] or line["exit"] == EXIT_TOOL or line["best_percent"] is None:
            continue
        if best is None or line["best_percent"] > best["best_percent"]:
            best = line
    hit = next((line["sweep_hit"][:_TEXT_CAP] for line in lines if line["sweep_hit"]), None)
    if best is None:
        return CheckSummary(len(lines), None, None, hit)
    return CheckSummary(len(lines), float(best["best_percent"]), best["source"], hit)


# ---- the v2 record's evidence (07-23; DEC-07, research section J, P10) ----


def _items(value: object) -> list:
    return value if isinstance(value, list) else []


def _json_file(path: Path) -> Mapping:
    """A JSON object file, {} when it is missing, unreadable or not an object."""
    data = _read(path)
    try:
        doc = json.loads(data) if data is not None else None
    except ValueError:
        return {}
    return doc if isinstance(doc, dict) else {}


def _record_text(value: object) -> str:
    """A short string fit for a record: long hex runs masked, capped at _TEXT_CAP."""
    return _LONG_HEX.sub("<hex>", str(value))[:_TEXT_CAP]


def _perfect_cell(cell: object) -> bool:
    """A measured sweep cell at objdiff 100% with a passing relocation check and no differing
    byte (attempt._is_hit without the default-flags test)."""
    return (isinstance(cell, Mapping) and cell.get("status") == attempt.MEASURED
            and _number(cell.get("objdiff_percent")) and cell["objdiff_percent"] == PERFECT
            and cell.get("reloc_ok") is True and cell.get("differing") == 0)  # fmt: skip


def _cell_spec(cell: Mapping) -> str:
    """A cell's compiler and flags as one spec (attempt._cell_spec's form)."""
    return " ".join([str(cell.get("compiler")), *map(str, _items(cell.get("flags")))])


def _sweep_evidence(attempt_dir: Path) -> tuple[str | None, list[str]]:
    """P10: the snapshot of the first checks.jsonl sweep line that has a hit (`checks/NNNN.c`)
    and the spec of every 100% cell of its saved JSON (`checks/NNNN.json`), stage 1 then stage
    2 (07-14), each once; (None, []) when no sweep hit. A missing or unreadable JSON keeps the
    source and names no cell."""
    path = Path(attempt_dir) / attempt.CHECK_LOG
    if not path.is_file():
        return None, []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = (line for raw in text.splitlines() if (line := _check_line(raw)) is not None)
    hit = next((line for line in lines if line["sweep"] and line["sweep_hit"]), None)
    if hit is None:
        return None, []
    source = hit["source"]
    doc = _json_file(Path(attempt_dir) / PurePosixPath(source).with_suffix(".json"))
    stage2 = doc.get("stage2")
    cells = [*_items(doc.get("cells")),
             *_items(stage2.get("cells") if isinstance(stage2, Mapping) else None)]  # fmt: skip
    specs = [_record_text(_cell_spec(cell)) for cell in cells if _perfect_cell(cell)]
    return source, list(dict.fromkeys(specs))


def _hook_blocks(events: Sequence[Mapping]) -> int:
    """The hook blocks of one session: the length of its last result event's
    `permission_denials` (research section 3: hook and permission-mode denials alike)."""
    results = [e for e in events if isinstance(e, Mapping) and e.get("type") == "result"]
    return len(_items(results[-1].get("permission_denials"))) if results else 0


def matched_starts(data: bytes | None, unit: str | None = None) -> frozenset[int]:
    """The starts of the `matched` rows of a status.csv's bytes (None: no table), only those of
    `unit` when one is given. Read loosely (any column order, `#` lines skipped), since only
    start, unit and status are needed."""
    if not data:
        return frozenset()
    text = data.decode("utf-8", "replace").splitlines()
    out: set[int] = set()
    for row in csv.DictReader(line for line in text if line and not line.startswith("#")):
        start = row.get("start")
        if row.get("status") != STATUS_MATCHED or not isinstance(start, str):
            continue
        if unit is not None and row.get("unit") != unit:
            continue
        try:
            out.add(int(start, 16))
        except ValueError:
            continue
    return frozenset(out)


def _function_passes(fn: Mapping) -> bool:
    """A gate check's function verdict: objdiff 100%, relocations and bytes ok."""
    reloc, same = fn.get("reloc"), fn.get("bytes")
    return (_number(fn.get("objdiff_percent")) and fn["objdiff_percent"] == PERFECT
            and isinstance(reloc, Mapping) and reloc.get("ok") is True
            and isinstance(same, Mapping) and same.get("ok") is True)  # fmt: skip


def _same_exe(name: object, exe: str) -> bool:
    """A check's `exe` (absent, a stem or an EXE file name) names `exe`."""
    return name is None or (isinstance(name, str) and PurePosixPath(name).stem.lower() == exe)


def _va(fn: Mapping) -> int | None:
    try:
        return int(fn["va"], 16)
    except (KeyError, TypeError, ValueError):
        return None


def _checked(doc: Mapping | None, exe: str) -> dict[int, bool]:
    """Each start a gate's checks of `exe` list, and whether it passed."""
    seen: dict[int, bool] = {}
    checks = doc.get("checks") if isinstance(doc, Mapping) else None
    for check in _items(checks):
        if not isinstance(check, Mapping) or not _same_exe(check.get("exe"), exe):
            continue
        for fn in _items(check.get("functions")):
            va = _va(fn) if isinstance(fn, Mapping) else None
            if va is not None:
                seen[va] = seen.get(va, True) and _function_passes(fn)
    return seen


def regressions(doc: Mapping | None, pick: Pick, before: Iterable[int], *,
                mismatch: bool = False) -> list[int]:  # fmt: skip
    """The previously matched starts (`before`: the claimed unit's matched rows right before
    the gate) that the gate found failing, sorted, each once; the claimed function is never
    one. A gate that refused the unit (`mismatch`, exit 1) lists a function that went back to
    INCLUDE_ASM in its problems only, never in its checks (the reverted-unit early return,
    cross_check: fix round 1), so then every such start counts unless a check shows it
    passing."""
    seen = _checked(doc, pick.exe)
    starts = sorted(set(before) - {pick.start})
    if mismatch:
        return [va for va in starts if not seen.get(va, False)]
    return [va for va in starts if seen.get(va) is False]


def _gate_field(gate: GateRun | None, pick: Pick) -> dict | None:
    """DEC-07's `gate` of a v2 attempt record: null when no gate ran, else its exit, whether it
    passed with a matched row for the claimed function, how many previously matched functions
    it found failing, and its problems as text."""
    if gate is None:
        return None
    doc = gate.doc if isinstance(gate.doc, Mapping) else {}
    problems = [_record_text(p) for p in _items(doc.get("problems"))][:_LISTED_CAP]
    return {"exit": gate.exit_code if _is_int(gate.exit_code) else None,
            "claimed_ok": gate.exit_code == EXIT_OK and claimed_matched(doc, pick),
            "regressions": len(regressions(doc, pick, gate.matched_before,
                                           mismatch=gate.exit_code == EXIT_MISMATCH)),
            "problems": problems}  # fmt: skip


def c_name(pick: Pick) -> str:
    """DEC-07 with D-19: a v2 record's `function`, the pick's C name (score.candidates names a
    pick through the EXE's symbol table), else the placeholder. Ruling F12: aborts too."""
    return pick.name if _C_NAME.fullmatch(pick.name or "") else f"func_{pick.start:08X}"


# ---- the difficult list (D-07) ----


def _key_text(key: Key) -> dict:
    return {"exe": key[0], "start": f"0x{key[1]:08X}"}


def _key(entry: object) -> Key:
    if not isinstance(entry, Mapping):
        raise DriverError(f"difficult entry {entry!r} is not an object")
    exe, start = entry.get("exe"), entry.get("start")
    if not isinstance(exe, str) or not isinstance(start, str) or not start.startswith("0x"):
        raise DriverError(f"difficult entry {entry!r} needs exe and a 0x start")
    return exe, int(start, 16)


def load_difficult(path: Path) -> dict[Key, tuple[Key, ...]]:
    """build/driver/difficult.json: each capped (EXE, start) and the callees matched when it
    was capped (picker.requeue's input). A missing file is an empty list."""
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        entries = doc["difficult"]
        return {_key(e): tuple(_key(c) for c in e.get("matched_callees", ())) for e in entries}
    except (ValueError, KeyError, TypeError) as exc:
        raise DriverError(f"{path} is not a difficult list: {exc}") from exc


def _log_records(log: Path) -> Iterator[dict]:
    """Each record of an attempts.jsonl, validated; a line that is not one is a DriverError
    naming its number. A missing log has none."""
    path = Path(log)
    if not path.is_file():
        return
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
            validate_record(record)
        except ValueError as exc:  # json's and RecordError
            raise DriverError(f"{path} line {number}: {exc}") from None
        yield record


def pass_index(log: Path) -> dict[Key, int]:
    """D-08, D-09: each function's finished passes, from attempts.jsonl alone (committed, so
    the count survives runs; build/driver/difficult.json is only a cache). A v2 attempt
    record names its pass; for v1 lines (the Phase 6 pilot) each run's attempts on a function
    form one pass. A function's count is the larger of the two, since the first v2 pass after
    v1 runs is numbered after them. Abort, run, limit and rename records are no sessions."""
    v1_runs: dict[Key, set[str]] = {}
    v2_pass: dict[Key, int] = {}
    for record in _log_records(log):
        if record["kind"] != KIND_ATTEMPT:
            continue
        key = (record["exe"], int(record["start"], 16))
        if "schema" in record:
            v2_pass[key] = max(v2_pass.get(key, 0), record["pass"])
        else:
            v1_runs.setdefault(key, set()).add(record["run"])
    return {key: max(len(v1_runs.get(key, ())), v2_pass.get(key, 0))
            for key in v1_runs.keys() | v2_pass.keys()}  # fmt: skip


def passes_of(log: Path, key: Key) -> int:
    """The finished passes of one function (`pass_index`); its next pass is one more."""
    return pass_index(log).get(key, 0)


def save_difficult(path: Path, difficult: Mapping[Key, Sequence[Key]]) -> None:
    entries = [{**_key_text(key), "matched_callees": [_key_text(c) for c in callees]}
               for key, callees in difficult.items()]  # fmt: skip
    write_atomic(path, (json.dumps({"difficult": entries}, indent=2) + "\n").encode("utf-8"))


# ---- unit claims (D-06) ----


class Claims:
    """D-06: one claim file per unit, build/driver/claims/<exe>__<unit>.json under `root` (the
    checkout), created with O_CREAT|O_EXCL (`_O_NEW`), so of any number of takers exactly one
    wins and no claim is ever overwritten. The body is one JSON object with CLAIM_KEYS (UTC ISO
    `claimed_at`). A claim is released by unlink after its landing decision."""

    def __init__(self, root: Path, run: str) -> None:
        self.root = Path(root)
        self.run = run
        self.directory = self.root / CLAIMS_DIR

    def path(self, exe: str, unit: str) -> Path:
        """The claim file of `exe`/`unit`; a name that could leave the claims directory is a
        DriverError."""
        if not (_CLAIM_FIELDS["exe"](exe) and _CLAIM_FIELDS["unit"](unit)):
            raise DriverError(f"no claim name for {exe!r}/{unit!r}")
        return self.directory / f"{exe}__{unit}.json"

    def take(self, record: Mapping) -> bool:
        """Create the unit's claim holding `record`; False when the unit is already claimed."""
        missing = sorted(set(CLAIM_KEYS) - set(record))
        if missing:
            raise DriverError(f"a claim needs {', '.join(missing)}")
        path = self.path(record["exe"], record["unit"])
        data = (json.dumps(dict(record), separators=(",", ":")) + "\n").encode("utf-8")
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, _O_NEW, 0o644)
        except FileExistsError:
            return False
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
        except BaseException:
            path.unlink(missing_ok=True)  # a half-written claim is never left behind
            raise
        return True

    def release(self, exe: str, unit: str) -> None:
        """Unlink the unit's claim (gone already: nothing to do)."""
        self.path(exe, unit).unlink(missing_ok=True)

    def recover(self) -> list[dict]:
        """D-06's stale rule, only with drive.lock held (a DriverError otherwise, nothing
        moved): every claim whose `run` is not this run was left by a dead drive, so it is
        moved (os.replace) to build/driver/<run>/stale-claims/. A claim that cannot be read
        names run "unknown". Returns {exe, unit, run} per moved claim, by file name."""
        probe = ProcessLock(self.root / DRIVE_LOCK)
        if probe.try_acquire():
            probe.release()
            raise DriverError(f"stale claims are recovered only with {DRIVE_LOCK.as_posix()} held")
        if not self.directory.is_dir():
            return []
        stale = self.root.joinpath(DRIVER_DIR, self.run, STALE_CLAIMS)
        found = []
        for path in sorted(self.directory.iterdir()):
            if path.suffix != ".json" or _is_link(path) or not path.is_file():
                continue
            run = _claim_run(path)
            if run == self.run:
                continue
            stale.mkdir(parents=True, exist_ok=True)
            os.replace(path, stale / path.name)
            exe, _, unit = path.stem.partition("__")
            found.append({"exe": exe, "unit": unit, "run": run or "unknown"})
        return found


def _claim_run(path: Path) -> str | None:
    """The `run` of a claim file, None when it cannot be read or names no valid run."""
    try:
        doc = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    run = doc.get("run") if isinstance(doc, dict) else None
    return run if isinstance(run, str) and _RUN_ID.fullmatch(run) else None


def recovered_detail(recovered: Sequence[Mapping]) -> str | None:
    """The STARTED record's detail naming each recovered claim (07-23: the v2 `recovered` field
    lists them too), or None when there is none."""
    if not recovered:
        return None
    return "recovered stale claims: " + _listed(
        [f"{c['exe']}/{c['unit']} (run {c['run']})" for c in recovered])


# ---- one claim ----


@dataclass(frozen=True)
class _Claim:
    """One session's claim and where its files go: the attempt dir under `runs` (build/driver,
    or the canary's build/driver/canary) and, inside it, the private view (D-24)."""

    pick: Pick
    run: str
    repo: Path
    n: int
    runs: Path = DRIVER_DIR
    pass_n: int = 1  # 07-23 (D-08): this function's pass, from the committed log
    model: str = MODEL  # 07-30 (D-09): the requested model, session.model_for_pass(pass_n)
    budget_usd: float = MAX_BUDGET_USD  # 07-30 (D-07, D-25): that model's per-session budget
    session: str = MATCHING_KIND  # 07-34 (D-18): the night's session kind (DriveConfig.session)

    @property
    def key(self) -> Key:
        return self.pick.exe, self.pick.start

    @property
    def function(self) -> str:
        return f"func_{self.pick.start:08X}"

    @property
    def target(self) -> str:
        return f"{self.pick.exe}/{self.pick.unit}"

    @property
    def unit_rel(self) -> str:
        return f"src/{self.pick.exe}/{self.pick.unit}.c"

    @property
    def status_rel(self) -> str:
        return f"config/{self.pick.exe}/status.csv"

    @property
    def attempt_dir(self) -> Path:
        return self.repo.joinpath(self.runs, self.run, self.pick.exe, self.function,
                                  f"attempt-{self.n}")  # fmt: skip

    @property
    def notes(self) -> Path:
        return self.attempt_dir / attempt.NOTES_FILE

    @property
    def notes_rel(self) -> str:
        return self.notes.relative_to(self.repo).as_posix()

    @property
    def view_root(self) -> Path:
        """<attempt dir>/view: HEAD's src/, include/ and config/ for this session (D-24)."""
        return self.attempt_dir / attempt.VIEW_DIR

    @property
    def view_unit(self) -> Path:
        """The only C file the session edits: <view>/src/<exe>/<unit>.c (absolute)."""
        return self.view_root.joinpath(attempt.VIEW_SRC, self.pick.exe, f"{self.pick.unit}.c")

    @property
    def view_unit_rel(self) -> str:
        return self.view_unit.relative_to(self.repo).as_posix()

    @property
    def proposals(self) -> Path:
        """<attempt dir>/proposals.jsonl, the session's naming proposals (D-19)."""
        return self.attempt_dir / attempt.PROPOSALS_FILE

    @property
    def proposals_rel(self) -> str:
        return self.proposals.relative_to(self.repo).as_posix()

    def env(self, base: Mapping[str, str]) -> dict[str, str]:
        """The session's environment: the base plus the four claim variables and the three
        view variables (absolute, F28; 07-13, D-24) that the hooks and the wrapper validate."""
        return {**base, attempt.CLAIM_ENV: self.target, attempt.FUNC_ENV: self.function,
                attempt.DIR_ENV: str(self.attempt_dir),
                attempt.NOTES_ENV: str(self.notes),
                hooks.UNIT_FILE_ENV: str(self.view_unit),
                hooks.PROPOSALS_ENV: str(self.proposals),
                hooks.SESSION_KIND_ENV: self.session,
                OPTIONAL_LOCKS: "0",  # D-27 P4: the session's git reads never take index.lock
                "PYTHONDONTWRITEBYTECODE": "1"}  # fmt: skip  # fix round 1 minor 3: no .pyc


@dataclass(frozen=True)
class _Snapshot:
    """The tree as the driver saw it right before or after a session (F3): each `git status`
    path with its entry and content hash, the bytes of each such file (so a stray edit of a
    file the driver itself had changed goes back to these bytes), and the bytes (None:
    missing) of each pinned path outside git's view (security ruling)."""

    status: dict[str, tuple[str, str | None]]
    data: dict[str, bytes]
    pinned: dict[str, bytes | None]
    prints: dict[str, tuple[int, int]]  # venv site-packages and repo __pycache__: size, mtime_ns


@dataclass(frozen=True)
class _Session:
    """A finished (or raised) session and what the driver measured around it."""

    claim: _Claim
    result: SessionResult | None
    pack: PackInfo
    seconds: float
    changed: tuple[str, ...]  # paths whose status entry or content changed during the session
    scaffolded: bool  # the view unit was scaffolded (HEAD has no such unit)
    unit_before: bytes  # the view unit's bytes at launch
    before: _Snapshot
    pinned_changed: tuple[str, ...] = ()  # pinned paths outside git's view that changed
    print_changed: tuple[str, ...] = ()  # fingerprinted files added, removed or changed
    view_head: str = ""  # the commit the view was taken from (F34)
    after: dict[str, tuple[str, str | None]] = field(default_factory=dict)  # git status after
    view_hashes: dict[str, str] = field(default_factory=dict)  # the view at launch (D-24, b)

    @property
    def events(self) -> tuple[dict, ...]:
        return self.result.events if self.result is not None else ()

    @property
    def disposition(self) -> Disposition:
        r = self.result
        return streamjson.classify(r.events, r.exit_code, r.timed_out)

    @property
    def counted(self) -> bool:
        return self.result is not None and self.disposition is Disposition.ATTEMPT_DONE

    @property
    def init(self) -> Mapping:
        return streamjson.init_event(self.events) or {}

    @property
    def usage(self) -> streamjson.Usage:
        results = [e for e in self.events if e.get("type") == "result"]
        return streamjson.usage(results[-1] if results else {})

    def text(self, key: str) -> str | None:
        """A short init field (model, CLI version) fit for a record, else None."""
        value = self.init.get(key)
        if not isinstance(value, str) or len(value) > _TEXT_CAP or _LONG_HEX.search(value):
            return None
        return value

    def has_work(self) -> bool:
        """The session changed its view unit (D-24)."""
        return _read(self.claim.view_unit) != self.unit_before


class _Ledger:
    """D-24 invariant (a): the bytes the driver itself last wrote to each driver-owned file
    git can see (progress/attempts.jsonl, config/<exe>/status.csv, the feed); a path the driver
    has not written yet is expected to hold HEAD's bytes (`head`). After a session each such
    path must hold exactly these bytes, unstaged, and every other path git can see must equal
    HEAD. This replaces the pre-session snapshot as the audit's reference, so the check no
    longer depends on a quiet tree between sessions (07-18, 07-21).

    Fix round 1: before every driver write of such a path the file must still hold the
    expected bytes (`holds`), else the night stops as a guardrail breach; after the write the
    ledger records the bytes the driver computed it wrote (`set`: the earlier bytes plus the
    appended line, a truncated prefix, the pre-gate bytes put back), never a read-back. The one
    residual is the gate itself: `gate` and `gate --partial` are subprocesses that write
    status.csv and the feed, so their output is read back (`note`), but only after the driver
    checked that both files held the expected bytes when the gate started. A change made by
    someone else while the gate runs is therefore taken for the gate's output."""

    def __init__(self, repo: Path, head: Callable[[str], bytes | None] | None = None) -> None:
        self.repo = Path(repo)
        self._bytes: dict[str, bytes | None] = {}
        self._head = head

    def note(self, *rels: str) -> None:
        """Record the current bytes (None: no file) of each repo-relative path: only for what a
        gate subprocess wrote (see the class docstring)."""
        for rel in rels:
            self._bytes[rel] = _read(self.repo / rel)

    def set(self, rel: str, data: bytes | None) -> None:
        """Record the bytes the driver itself just wrote to `rel` (None: it removed it)."""
        self._bytes[rel] = data

    def expected(self, rel: str) -> bytes | None:
        """The bytes `rel` must hold now: the driver's last write, else HEAD's (None: none)."""
        if rel in self._bytes:
            return self._bytes[rel]
        return self._head(rel) if self._head is not None else None

    def holds(self, rel: str) -> bool:
        """`rel` is a regular file (never a link) with the expected bytes, or absent when no
        bytes are expected."""
        path = self.repo / rel
        if _is_link(path):
            return False
        return _read(path) == self.expected(rel) and (path.is_file() or not path.exists())

    def knows(self, rel: str) -> bool:
        return rel in self._bytes

    def bytes_of(self, rel: str) -> bytes | None:
        return self._bytes.get(rel)

    def matches(self, rel: str) -> bool:
        """The file holds exactly the bytes the driver last wrote (a missing file matches a
        noted absence only)."""
        return rel in self._bytes and _read(self.repo / rel) == self._bytes[rel]

    def paths(self) -> list[str]:
        return sorted(self._bytes)


def _truncate(path: Path, size: int) -> bool:
    """F19: cut `path` back to `size` bytes (never longer than it is), never through a link;
    False when it is a link or not a regular file."""
    if _is_link(path) or not path.is_file():
        return False
    with path.open("r+b") as fh:
        if fh.seek(0, os.SEEK_END) > size:
            fh.truncate(size)
    return True


@dataclass
class _Contained:
    """What containment did, file by file (fourth security pass)."""

    restored: list[str] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)
    not_contained: list[str] = field(default_factory=list)
    not_restored: list[str] = field(default_factory=list)
    unstage_failed: list[str] = field(default_factory=list)  # bytes back, index entry not
    refused: list[str] = field(default_factory=list)


class _Breach(Exception):
    """Fix round 1: a driver-owned file no longer held the driver's bytes right before the
    match commit; `detail` already describes the containment."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class _Kept(Exception):
    """07-21 fix round 2 (N2, N4): the driver's match commit exists and HEAD is left where it
    is (a foreign commit came in, HEAD could not be moved back, or the post-commit check
    itself failed). Nothing is undone under the kept commit; the night stops `guardrail`
    and `detail` says why."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class _Stop(Exception):
    """Ends the night with a STOPPED record. After any breach (containment ran) nothing is
    committed, whatever the reason (fix round 2, J2)."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = _detail(detail)


class _Halt(Exception):
    """07-21: the night is stopping because of another worker (or an interrupt): this worker
    contained and reset what it had and leaves quietly. `note` names what its containment did
    (empty: nothing to report); the first failure alone writes the STOPPED record."""

    def __init__(self, note: str = "") -> None:
        super().__init__(note)
        self.note = note


_TICK_S = 0.2  # the coordinator's wait between checks, so the main thread sees an interrupt


class _Pause:
    """D-07 with Phase 6 D-08: one usage-limit pause shared by every worker, under the
    night's condition `cond`. A session that ends LIMIT while no pause holds starts it
    (`on_limit`): its worker waits the backoff (60, 120, 240 s, then 300 s polls by the shared
    `streak`) while no worker launches (`wait_to_launch` blocks); sessions already running
    finish and are salvaged or judged as usual. When the backoff ends (`backoff_done`)
    exactly one launch is the probe (`probe_taken`): a probe that is not LIMIT clears the
    pause for all and restarts the streak (`on_clear`); another LIMIT renews the pause one
    step longer. A LIMIT from a session launched before the pause leaves it as it is. With one
    worker every launch after a LIMIT is the probe, which is the Phase 6 backoff exactly."""

    def __init__(self, cond: threading.Condition, stop: threading.Event,
                 clock: Callable[[], float]) -> None:  # fmt: skip
        self.cond = cond
        self.stop = stop
        self.clock = clock
        self.paused = False
        self.paused_until = 0.0  # on `clock`: when the current backoff ends
        self.streak = 0
        self.due = False  # the backoff has been waited: the next launch is the probe
        self.probe_taken = False
        self.waiting = 0  # workers held right now (announced on `cond`)

    def wait_to_launch(self) -> bool:
        """Block while the pause holds; True when this launch is the probe. A stopping night
        raises _Halt instead (nothing launches any more)."""
        with self.cond:
            self.waiting += 1
            self.cond.notify_all()
            try:
                while True:
                    if self.stop.is_set():
                        raise _Halt()
                    if not self.paused:
                        return False
                    if self.due and not self.probe_taken:
                        self.probe_taken = True
                        return True
                    self.cond.wait(_TICK_S)
            finally:
                self.waiting -= 1

    def on_limit(self, probe: bool) -> tuple[int, int] | None:
        """A session ended LIMIT: start (or, for the probe, renew) the pause and return the
        backoff its worker waits and the streak it makes (1 for the first wait); None when a
        pause already holds (the session ran before). 07-23: its worker then writes the limit
        record, outside the condition (lock order: gate, then cond)."""
        with self.cond:
            if self.paused and not probe:
                return None
            seconds = BACKOFF_S[self.streak] if self.streak < len(BACKOFF_S) else POLL_S
            self.streak += 1
            self.paused, self.due, self.probe_taken = True, False, False
            self.paused_until = self.clock() + seconds
            self.cond.notify_all()
            return seconds, self.streak

    def backoff_done(self) -> None:
        """The backoff has been waited: the next launch, by any worker, is the probe."""
        with self.cond:
            self.due = True
            self.cond.notify_all()

    def on_clear(self, probe: bool) -> None:
        """A session that was not LIMIT: the probe clears the pause for every worker and the
        streak starts again; any other session leaves a holding pause alone."""
        with self.cond:
            if probe or not self.paused:
                self.paused, self.due, self.probe_taken, self.streak = False, False, False, 0
                self.cond.notify_all()


class _Worker:
    """D-06: one worker of the night, numbered `ident` (0..workers-1, the claim's `worker`). It
    runs one function's pass (`_Night._function`: up to attempts_per_function sessions, each
    under its unit's claim) and hands any failure to the night, which stops every other
    worker (stop-all). With one worker the pass runs on the calling thread (`inline`), exactly
    the Phase 6 driver; otherwise on its own thread."""

    def __init__(self, coordinator: _Coordinator, ident: int, pick: Pick,
                 difficult: dict[Key, tuple[Key, ...]]) -> None:  # fmt: skip
        self.coordinator = coordinator
        self.night = coordinator.night
        self.ident = ident
        self.pick = pick
        self.difficult = difficult
        self.outcome: str | None = None  # the pass's end (`_Night._function`), None: cut short
        self.thread = threading.Thread(target=self._run, name=f"drive-worker-{ident}",
                                       daemon=True)  # fmt: skip

    def inline(self) -> None:
        """The pass on the calling thread; a failure propagates as in Phase 6."""
        self.night.local.worker = self.ident
        try:
            self.outcome = self.night._function(self.pick, self.difficult)
        finally:
            self.coordinator.release(self)

    def _run(self) -> None:
        night = self.night
        night.local.worker = self.ident
        try:
            self.outcome = night._function(self.pick, self.difficult)
        except _Halt as halt:
            night._note(halt.note)
        except BaseException as exc:  # noqa: BLE001 - handed to the main thread (stop-all)
            night._fail(exc)
        finally:
            self.coordinator.release(self)


class _Coordinator:
    """D-06, D-07: the main thread's part of the night. It owns the picker: it hands each
    function's pass to a free worker, skipping for now (never dropping) a pick whose unit
    another worker's pass holds, and stops handing out passes once the night ends (the caps,
    or a stop). Claims, counters and locks stay the night's (`_Night`), shared by every
    worker; every shared write goes through the gate lock, every git call through the git
    lock. Returns the night's end reason, or re-raises the first worker's failure once every
    worker has finished.

    With a tier queue (07-26) the coordinator asks it, under the night's condition, for the
    best eligible pick each time a worker is free (the busy units are its claimed units), marks
    the pick in flight and tells the queue how the pass ended when the worker is released: a
    capped function returns for its next pass (D-08) and the night's `passes`, which the queue
    reads, already counts it. Nothing eligible while a pass runs: wait for it; nothing
    eligible and nothing running: the queue is done."""

    def __init__(self, night: _Night) -> None:
        self.night = night
        self.free = list(range(night.config.workers))  # the idle workers' numbers
        self.busy: dict[tuple[str, str], _Worker] = {}  # (exe, unit) -> the worker on it
        self.threads: list[threading.Thread] = []
        self.deferred: list[Pick] = []  # picks whose unit was busy, in queue order
        self.picks: Iterator[Pick] = iter(())
        self.tiers: TierQueue | None = None  # 07-26: the tier queue, when a tier is signed
        self.exhausted = False
        self.picked = False

    def run(self) -> str:
        night = self.night
        difficult = night._difficult()
        source = night.deps.queue(frozenset(difficult))
        if isinstance(source, TierQueue):
            source.use_passes(night.passes)  # one pass index: the records' and the queue's
            self.tiers = source
        else:
            self.picks = iter(source)
        try:
            while (pick := self._next()) is not None:
                self.picked = True
                self._dispatch(pick, difficult)
            self._drain()
        except BaseException as exc:  # an interrupt on the main thread: stop every worker first
            night._stop_all()
            self._drain()
            if not isinstance(exc, Exception) and self.threads:
                night.interrupted += night._stopped_workers()
            raise
        night._raise_failure()
        with night.cond:
            end = night._end()
        if end:
            return end
        return QUEUE_EXHAUSTED if self.picked else NOTHING_TO_DO

    def release(self, worker: _Worker) -> None:
        """A worker's pass ended: its unit and its number are free again."""
        with self.night.cond:
            self.busy.pop((worker.pick.exe, worker.pick.unit), None)
            if self.tiers is not None:
                self.tiers.finish((worker.pick.exe, worker.pick.start),
                                  matched=worker.outcome == MATCHED,
                                  aborted=worker.outcome == ABORTED,
                                  capped=worker.outcome == CAPPED)  # fmt: skip
            self.free.append(worker.ident)
            self.free.sort()
            self.night.cond.notify_all()

    def _next(self) -> Pick | None:
        """The next pick for a free worker, or None when the night hands out no more: stopping,
        a cap reached (D-07), or no pick left (every deferred one has run)."""
        night = self.night
        with night.cond:
            while True:
                if night.stop.is_set() or night._end():
                    return None
                if self.free:
                    pick = self._eligible()
                    if pick is not None:
                        return pick
                    if self.exhausted and not self.deferred:
                        return None
                night.cond.wait(_TICK_S)

    def _eligible(self) -> Pick | None:
        """The first deferred pick whose unit is free, else the queue's next new pick; a pick
        whose unit is busy is deferred, a pick already taken tonight is skipped."""
        if self.tiers is not None:
            return self._tier_pick()
        for i, pick in enumerate(self.deferred):
            if (pick.exe, pick.unit) not in self.busy:
                return self.deferred.pop(i)
        while not self.exhausted:
            pick = next(self.picks, None)
            if pick is None:
                self.exhausted = True
                break
            key = (pick.exe, pick.start)
            if key in self.night.done:
                continue
            self.night.done.add(key)
            if (pick.exe, pick.unit) in self.busy:
                self.deferred.append(pick)
                continue
            return pick
        return None

    def _tier_pick(self) -> Pick | None:
        """07-26: the tier queue's best eligible pick outside the busy units, now in flight.
        None with no pass running ends the queue: nothing can become eligible tonight."""
        pick = self.tiers.next_eligible(frozenset(self.busy))
        if pick is None:
            self.exhausted = not self.busy
            return None
        self.tiers.take((pick.exe, pick.start))
        return pick

    def _dispatch(self, pick: Pick, difficult: dict[Key, tuple[Key, ...]]) -> None:
        with self.night.cond:
            worker = _Worker(self, self.free.pop(0), pick, difficult)
            self.busy[(pick.exe, pick.unit)] = worker
        if self.night.config.workers == 1:
            worker.inline()
            return
        self.threads.append(worker.thread)
        worker.thread.start()

    def _drain(self) -> None:
        """Wait for every started worker, in short joins so an interrupt reaches this thread."""
        for thread in self.threads:
            while thread.is_alive():
                thread.join(_TICK_S)


class _Night:
    def __init__(self, config: DriveConfig, deps: Deps) -> None:
        if not _RUN_ID.fullmatch(config.run_id):
            raise DriverError(f"run id {config.run_id!r} is not [A-Za-z0-9_.-]+")
        if config.workers < 1:
            raise DriverError(f"workers {config.workers} is below 1")
        if config.session not in SESSIONS:
            raise DriverError(f"session {config.session!r} is not one of {', '.join(SESSIONS)}")
        self.config = config
        self.deps = deps
        self.repo = Path(config.repo_root)
        self.log = self.repo / ATTEMPT_LOG
        self.sessions = 0
        self.matched = 0
        self.reserved = 0  # D-07: night-cap slots held by attempts not yet counted (_reserve)
        self.spent = 0  # 07-26 fix round 1: night-cap slots spent by transient launches (_spend)
        self.done: set[Key] = set()
        # D-06: per worker thread: `worker` (its number), `live` (its session to reset if a
        # later step raises) and `slot` (it holds a reserved slot of the night cap, D-07).
        self.local = threading.local()
        # 07-21: the coordinator's condition: the counters, the dispatch, the pause and the
        # stop. Taken only for short steps and never while waiting for the gate lock (order:
        # gate, then cond).
        self.cond = threading.Condition()
        self.stop = threading.Event()  # set by the first failure (stop-all) or an interrupt
        self.failure: BaseException | None = None  # the first worker failure, re-raised
        self.halt_notes: list[str] = []  # what each halted worker's containment did
        self.pause = _Pause(self.cond, self.stop, deps.clock)  # D-07: one for every worker
        # 07-21 stop-all: worker -> the pid of its live session (run_session's on_start/on_end)
        self.pids: dict[int, int] = {}
        self.pid_lock = threading.Lock()
        self.killed: list[int] = []  # the pids stop-all killed
        # 07-21 fix round 1 (C1): the pinned paths' bytes once, before the first launch. The
        # driver never writes them, so every launch, audit and containment compares with
        # (and restores to) this, never a session's own launch snapshot, which may hold
        # another live session's stray. None until the night starts (the canary's probe).
        self.pinned_base: dict[str, bytes | None] | None = None
        self.git_dir: Path | None = None
        self.interrupted = ""  # what containment did before an interrupt was re-raised
        self.breached = False  # sticky (J2): set once any containment ran; nothing is committed
        self.pre_gate: dict[str, bytes | None] = {}  # status.csv and the feed right before the gate
        self.landed: str | None = None  # the unit the landing section copied into src/ (D-24)
        self.ledger = _Ledger(self.repo, self._head_bytes)  # the driver's own writes (D-24 a)
        self.landed_bytes: bytes | None = None  # what the landing section wrote to src/
        self.undo_reason: str | None = None  # a breach's stop reason met by the last match undo
        self.claims = Claims(self.repo, config.run_id)  # D-06: one claim file per unit
        self.passes: dict[Key, int] = {}  # D-08: finished passes per function (pass_index)
        # 07-23 (DEC-06): each record this night appended, with its offset in the log, so the
        # totals are the sums over the night's own records (F19's cut drops a line from both).
        self.night_records: list[tuple[int, dict]] = []
        self.night_start = 0.0  # Deps.clock at the night's start: the totals' wall_seconds
        self.coordinator: _Coordinator | None = None
        # D-06, D-27 P4: one in-process lock around every shared write: the landing section
        # (copy, lint, gate, commit or undo, reset), `gate --partial` and every record append.
        # Reentrant, because the landing section appends its own record while it holds it.
        self.gate_lock = threading.RLock()
        self.git_lock = threading.Lock()  # D-27 P4: one driver git call at a time (_git)
        # 07-34 (D-19): rename and header proposals waiting for another live claim's release,
        # in proposal order (_retry_deferred).
        self.deferred_renames: list[_Pending] = []

    @property
    def live(self) -> _Session | None:
        """This worker's session to reset if a later step raises (D-06: one per worker)."""
        return getattr(self.local, "live", None)

    @live.setter
    def live(self, session: _Session | None) -> None:
        self.local.live = session

    @property
    def worker(self) -> int:
        """This thread's worker number (0 on the calling thread with one worker)."""
        return getattr(self.local, "worker", 0)

    # --- workers (07-21) ---

    def _reserve(self) -> bool:
        """D-07: the shared night cap. Before each launch but a LIMIT relaunch a worker reserves
        a slot while `sessions + spent + reserved < max_sessions`; the slot becomes a counted
        session (`_count`), a spent transient launch (`_spend`, 07-26 fix round 1: every
        launched session counts toward the cap, aborted ones included), or is given back when
        the attempt ends otherwise (`_release`). A LIMIT relaunch keeps its attempt's slot.
        While every free slot is reserved by attempts still running, the worker waits, since
        one may end uncounted. False: the night is ending (a cap reached, or a stop) and
        nothing more launches."""
        with self.cond:
            while True:
                if self.stop.is_set() or self._end():
                    return False
                if self.sessions + self.spent + self.reserved < self.config.max_sessions:
                    self.reserved += 1
                    self.local.slot = True
                    return True
                self.cond.wait(_TICK_S)

    def _release(self) -> None:
        """Give this worker's reserved slot back (an attempt that ended uncounted)."""
        with self.cond:
            if getattr(self.local, "slot", False):
                self.local.slot = False
                self.reserved -= 1
                self.cond.notify_all()

    def _spend(self) -> None:
        """A transient launch (07-26 fix round 1): this worker's reserved slot is spent, so the
        night cap bounds transient relaunches too; it is not a counted session."""
        with self.cond:
            self.spent += 1
            if getattr(self.local, "slot", False):
                self.local.slot = False
                self.reserved -= 1
            self.cond.notify_all()

    def _count(self) -> None:
        """One counted session (D-07, D-48), from any worker: its reserved slot becomes it."""
        with self.cond:
            self.sessions += 1
            if getattr(self.local, "slot", False):
                self.local.slot = False
                self.reserved -= 1
            self.cond.notify_all()

    def _fail(self, exc: BaseException) -> None:
        """A worker failed: the first failure is the night's, and every worker stops."""
        with self.cond:
            if self.failure is None:
                self.failure = exc
            elif isinstance(exc, _Stop):  # a later stop's containment is still reported
                self.halt_notes.append(f"{exc.reason}: {exc.detail}")
        self._stop_all()

    def _note(self, note: str) -> None:
        if note:
            with self.cond:
                self.halt_notes.append(note)

    def _stop_all(self) -> None:
        """Stop-all (D-08 with workers): no worker launches or lands anything more, and every
        live session tree in the pid registry is killed; each worker then contains and resets
        its own attempt (`_launch`) and leaves (_Halt)."""
        with self.cond:
            self.stop.set()
            self.cond.notify_all()
        with self.pid_lock:
            pids = sorted(set(self.pids.values()))
        for pid in pids:
            self._kill(pid)

    def _kill(self, pid: int) -> None:
        try:
            self.deps.kill(pid)
        except Exception:  # noqa: BLE001 - a tree already gone; its worker still contains it
            pass
        with self.pid_lock:
            self.killed.append(pid)

    def _on_start(self, pid: int) -> None:
        """run_session's on_start: this worker's session is live. Registered and checked under
        one lock, so a session that starts as the night stops is killed too."""
        with self.pid_lock:
            self.pids[self.worker] = pid
            stopping = self.stop.is_set()
        if stopping:
            self._kill(pid)

    def _on_end(self, pid: int) -> None:
        with self.pid_lock:
            if self.pids.get(self.worker) == pid:
                del self.pids[self.worker]

    def _stopped_workers(self) -> str:
        """What stop-all did on an interrupt, for the STOPPED `interrupted` record."""
        with self.pid_lock:
            killed = sorted(set(self.killed))
        text = "; every worker stopped"
        if killed:
            text += f"; killed the session trees of pids {', '.join(map(str, killed))}"
        # Fix round 1 (I2): a halted worker's own stop (its strays, what it quarantined) is
        # the night's `failure` here, never re-raised, so its detail goes into this record.
        failure = self.failure
        if isinstance(failure, _Stop):
            text += f"; {failure.reason}: {failure.detail}"
        elif failure is not None:
            text += f"; {type(failure).__name__}: {failure}"
        return "; ".join([text, *self.halt_notes])

    def _halt_if_stopping(self) -> None:
        """Between steps of a pass: leave quietly once the night is stopping."""
        if self.stop.is_set():
            raise _Halt()

    def _raise_failure(self) -> None:
        """Once every worker has finished: re-raise the first failure on this thread, with what
        each halted worker's containment did added to a stop's detail."""
        failure = self.failure
        if failure is None:
            return
        if isinstance(failure, _Stop) and self.halt_notes:
            raise _Stop(failure.reason, "; ".join([failure.detail, *self.halt_notes])) from failure
        raise failure

    # --- the night ---

    def run(self, lock: ProcessLock | None = None) -> DriveReport:
        """D-06: the night holds build/driver/drive.lock (an OS lock, freed by the kernel when
        this process exits) from before its STARTED record to its end. `lock` is the verb's,
        already held since before the preflight (07-18 fix round 1); without one the night
        takes its own and frees it at the end. Failing to get it refuses the start (exit 2, no
        record): another drive is running. Getting it proves every earlier holder dead; no
        process id is probed (D-24)."""
        if lock is not None:
            if not lock.held or Path(lock.path) != self.repo / DRIVE_LOCK:
                return DriveReport(REFUSED, "drive lock", 0, 0, "refusing to start: the drive "
                                   f"lock given is not {DRIVE_LOCK.as_posix()} held")  # fmt: skip
            return self._run_locked()
        try:
            own = take_drive_lock(self.repo)
        except Refused as refused:
            return DriveReport(REFUSED, refused.reason, 0, 0, refused.detail)
        try:
            return self._run_locked()
        finally:
            own.release()

    def _run_locked(self) -> DriveReport:
        """Every night ends with a run record (fix round 1, I1): ENDED, a STOPPED reason, a
        STOPPED `error` for any other exception, or a STOPPED `interrupted` for a
        KeyboardInterrupt/SystemExit, which is then re-raised (minor 8)."""
        try:
            dirty = self._dirty_outputs()
        except Exception as exc:  # fix round 4 L3: refused, never an escape
            why = _detail(
                f"refusing to start: the outputs check failed: {type(exc).__name__}: {exc}"
            )
            return DriveReport(REFUSED, "outputs check", 0, 0, why)
        if dirty:  # fix round 3 minor 1: never start on another night's leftovers
            detail = (
                f"refusing to start: {_listed(dirty)} differ from HEAD or are staged "
                "(an earlier night left them; inspect, then commit or restore them)"
            )
            return DriveReport(REFUSED, "dirty", 0, 0, detail)
        try:
            recovered = self.claims.recover()  # D-06: drive.lock is held, so they are stale
        except Exception as exc:
            why = _detail("refusing to start: stale claims could not be recovered: "
                          f"{type(exc).__name__}: {exc}")  # fmt: skip
            return DriveReport(REFUSED, "claims", 0, 0, why)
        self.night_start = self.deps.clock()
        try:
            self._record_run(STARTED, START, recovered_detail(recovered), recovered=recovered)
        except _Stop as stop:  # fix round 1: the log changed since the outputs check
            return DriveReport(REFUSED, stop.reason, 0, 0, stop.detail)
        failed: list[str] = []
        try:
            event, reason, detail = ENDED, self._loop(), None
            failed = [_detail(str(check)) for check in self.deps.end_of_run()]  # L1
        except _Stop as stop:
            event, reason, detail = STOPPED, stop.reason, stop.detail
        except Exception as exc:
            event, reason, detail = STOPPED, ERROR, _detail(f"{type(exc).__name__}: {exc}")
        except BaseException as exc:
            why = _detail(type(exc).__name__ + self.interrupted)
            self._record_run(STOPPED, INTERRUPTED, why, uncommitted=self._uncommitted_rows(),
                             guard=False)  # fmt: skip  # nothing is committed after an interrupt
            raise
        found = [] if self.breached else self._ledger_breaches()
        if found:  # fix round 1: never commit a driver-owned file holding bytes it did not write
            event, reason = STOPPED, GUARDRAIL
            detail = _detail("; ".join([*([detail] if detail else []), *found]))
        uncommitted = self._uncommitted_rows() if event == STOPPED else []
        self._record_run(event, reason, detail, checks_failed=failed, uncommitted=uncommitted)
        if (
            not self.breached
        ):  # fix round 2 J2: after any breach commit nothing, whatever the reason
            self._commit_log(stopped=event == STOPPED)
        return DriveReport(event, reason, self.sessions, self.matched, detail, tuple(failed))

    def _uncommitted_rows(self) -> list[str]:
        """Fix round 4 L2: each status.csv row that differs from HEAD (`<path>: <start>
        <status>`) and a changed feed, so the owner knows why the next drive is refused.
        Best-effort: a path that cannot be read is named as such."""
        out: list[str] = []
        for exe in EXE_ORDER:
            rel = f"config/{exe}/status.csv"
            try:
                out += self._new_rows(rel)
            except Exception as exc:  # noqa: BLE001 - named instead
                out.append(f"{rel}: unknown ({type(exc).__name__}: {exc})")
        try:
            if FEED in parse_status(_git_ok(self._git, ["status", "--porcelain=v1", "-z",
                                                            "--", FEED])):  # fmt: skip
                out.append(f"{FEED}: changed")
        except Exception as exc:  # noqa: BLE001 - named instead
            out.append(f"{FEED}: unknown ({type(exc).__name__}: {exc})")
        return [_detail(line) for line in out]

    def _new_rows(self, rel: str) -> list[str]:
        """The rows of `rel` that HEAD does not have, as `<rel>: <start> <status>`."""
        path = self.repo / rel
        now = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        head = set(_git_ok(self._git, ["show", f"HEAD:{rel}"]).decode("utf-8").splitlines())
        rows = [line.split(",") for line in now if line not in head and not line.startswith("#")]
        return [f"{rel}: {cells[0]} {cells[3]}" if len(cells) > 3 else f"{rel}: {cells[0]}"
                for cells in rows]  # fmt: skip

    def _outputs(self) -> list[str]:
        """The files the driver commits besides the unit: the log, both tables, the feed."""
        return [ATTEMPT_LOG.as_posix(), *(f"config/{exe}/status.csv" for exe in EXE_ORDER), FEED]

    def _dirty_outputs(self) -> list[str]:
        """Those of `_outputs` that differ from HEAD in the worktree or the index (fix round 3
        minor 1; 06-25's dirty-tree preflight is a second layer)."""
        paths = self._outputs()
        raw = _git_ok(self._git, ["status", "--porcelain=v1", "-z", "--", *paths])
        dirty = parse_status(raw)
        return [path for path in paths if path in dirty]

    def _commit_log(self, *, stopped: bool) -> None:
        """D-23: the night's remaining records in one `chore(driver): attempt log` commit, with
        the status tables and the feed when partial rows changed them. After a STOP only the log
        is committed: a gate that failed may have left a half-written table."""
        if self.coordinator is not None:  # research R5: only once every worker has drained
            self.coordinator._drain()
        paths = [ATTEMPT_LOG.as_posix()]
        if not stopped:
            paths += [*(f"config/{exe}/status.csv" for exe in EXE_ORDER), FEED]
        raw = _git_ok(self._git, ["status", "--porcelain=v1", "-z", "--", *paths])
        dirty = parse_status(raw)
        changed = [path for path in paths if path in dirty]
        if not changed:
            return
        message = f"{LOG_SUBJECT}\n\nAttempt records of run {self.config.run_id}.\n"
        message_file = self.repo.joinpath(DRIVER_DIR, self.config.run_id, LOG_MSG)
        self._commit_with_retry(message=message, message_file=message_file, paths=changed)

    def _git(self, args: Sequence[str], *, input: bytes | None = None
             ) -> subprocess.CompletedProcess:  # fmt: skip
        """Every driver git call, one at a time behind the git lock (D-27 P4). `input` is git's
        stdin (fix round 2); a call without one keeps the plain `git(args)` seam."""
        with self.git_lock:
            return self.deps.git(args) if input is None else self.deps.git(args, input=input)

    def _git_retry(self, args: list[str]) -> bytes:
        """`git --literal-pathspecs <args>`, retried once after INDEX_LOCK_WAIT_S when git
        names index.lock (someone else held the index); any other failure, or a second one,
        is a DriverError."""
        done = self._git([LITERAL, *args])
        if done.returncode != 0 and INDEX_LOCK in (done.stderr or b""):
            self.deps.sleep(INDEX_LOCK_WAIT_S)
            done = self._git([LITERAL, *args])
        return _git_stdout(done, args)

    def _commit_with_retry(self, *, message: str, message_file: Path,
                           paths: Sequence[str]) -> None:  # fmt: skip
        """`git add -- <paths>` (a new unit is untracked, F5), then `git commit -F <file> --
        <paths>`: explicit literal paths only, never `-A` or `.`; each step retried once on an
        index.lock error before the caller undoes the match (D-27 P4)."""
        message_file.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(message_file, message.encode("utf-8"))
        self._git_retry(["add", "--", *paths])
        self._git_retry(["commit", "-q", "-F", str(message_file), "--", *paths])

    def _end(self) -> str | None:
        """Why the night ends now (D-07): the match target (0: off), then the night cap, which
        counts every launched session: the counted ones and the spent transient launches (07-26
        fix round 1)."""
        with self.cond:
            target = self.config.target_matched
            if target and self.matched >= target:
                return TARGET_MATCHED
            if self.sessions + self.spent >= self.config.max_sessions:
                return MAX_SESSIONS
            return None

    def _loop(self) -> str:
        """The coordinator hands the picks to the workers (D-06); one worker is Phase 6's
        serial loop."""
        self._safe_dir(self._quarantine_root())  # third pass: before any session
        self.pinned_base = self._pinned_state()  # fix round 1 (C1): before the first launch
        with self.gate_lock:  # 07-23 (D-08): the log is read once, while no record is appended
            self.passes = pass_index(self.log)
        self.coordinator = _Coordinator(self)
        end = self.coordinator.run()
        self._retry_deferred()  # 07-34: every claim of the night is released now
        return end

    def _pinned_baseline(self, snapshot: _Snapshot) -> dict[str, bytes | None]:
        """The pinned bytes every check compares with: the night's baseline (C1), or, outside
        a night, the given snapshot's."""
        return self.pinned_base if self.pinned_base is not None else snapshot.pinned

    def _pinned_drift(self, snapshot: _Snapshot) -> list[str]:
        """The pinned paths whose bytes in `snapshot` differ from the baseline."""
        base = self._pinned_baseline(snapshot)
        return sorted(n for n in base.keys() | snapshot.pinned.keys()
                      if base.get(n) != snapshot.pinned.get(n))  # fmt: skip

    def _difficult(self) -> dict[Key, tuple[Key, ...]]:
        """The persisted difficult list, minus what `requeue` gives back (D-07)."""
        path = self.repo / DIFFICULT
        difficult = load_difficult(path)
        back = [key for key in self.deps.requeue(dict(difficult)) if key in difficult]
        for key in back:
            del difficult[key]
        if back:
            save_difficult(path, difficult)
        return difficult

    def _function(self, pick: Pick, difficult: dict[Key, tuple[Key, ...]]) -> str | None:
        """At most attempts_per_function counted sessions (D-07); a function that used them all
        without a match goes to the difficult list once and has finished a pass: its count in
        `passes` goes up, so a tier queue offers it again for its next pass (D-08). Returns
        MATCHED, CAPPED, ABORTED (a transient abort ended the pass; a tier queue sends it
        behind its group's other work) or None when the pass was cut short (the night cap, a
        stop). 07-38 (D-17): a readability night runs one session per unit and returns its
        outcome; nothing goes to the difficult list."""
        readability = self.config.session == READABILITY
        for n in range(1, self._attempts() + 1):
            if not self._reserve():  # D-07: no slot of the night cap is left, or a stop
                return None
            try:
                outcome = self._announced(pick, n)
            finally:
                self._release()  # not counted (a stop): a slot still held goes back
            if readability or outcome in (MATCHED, ABORTED, None):
                return outcome
        callees = tuple(self.deps.matched_callees(pick))
        key = (pick.exe, pick.start)
        with self.cond:  # the list and the pass counts are shared by every worker
            difficult[key] = callees
            save_difficult(self.repo / DIFFICULT, difficult)
            self.passes[key] = self.passes.get(key, 0) + 1
        return CAPPED

    def _attempts(self) -> int:
        """Sessions per pass: attempts_per_function (D-07); one per unit on a readability night
        (07-38, D-17)."""
        return 1 if self.config.session == READABILITY else self.config.attempts_per_function

    def _model(self, pick: Pick) -> str:
        """The requested model of `pick`'s session: the pass's (D-09) on a matching night, Opus
        on a readability night (07-38: escalation is a matching rule)."""
        return OPUS_MODEL if self.config.session == READABILITY else model_for_pass(
            self._pass(pick))  # fmt: skip

    def _label(self, pick: Pick, n: int) -> str:
        return f"{pick.exe} func_{pick.start:08X} attempt {n}/{self._attempts()}"

    def _announced(self, pick: Pick, n: int) -> str | None:
        """Quick 261026-9ue: one start and one outcome line per attempt. The seconds are the
        attempt's wall time on Deps.clock, relaunches, backoffs and the gate included (the
        record's `seconds` is the session alone). A stop or an interrupt prints no outcome line:
        the STOPPED summary names why."""
        label = self._label(pick, n)
        self.deps.say(f"{label}: started")
        start = self.deps.clock()
        outcome = self._guarded(pick, n)
        shown = f"ABORTED ({TRANSIENT})" if outcome in (ABORTED, None) else outcome
        self.deps.say(f"{label}: {shown} after {self.deps.clock() - start:.1f} s")
        return outcome

    def _guarded(self, pick: Pick, n: int) -> str | None:
        """One attempt under its unit's claim; any unexpected failure resets the live session
        and stops the night. The reset comes before the claim is released (D-06)."""
        with self._claimed(pick):
            try:
                return self._attempt(pick, n)
            except (_Stop, _Halt):
                raise
            except Exception as exc:
                self._reset_live()
                raise _Stop(ERROR, f"{type(exc).__name__}: {exc}") from exc
            except BaseException:
                self._reset_live()  # minor 8: an interrupt between steps still resets the attempt
                raise
            finally:
                self.live = None

    @contextmanager
    def _claimed(self, pick: Pick) -> Iterator[None]:
        """D-06: the unit's claim file, taken before the attempt's first view is made and
        released after its landing decision, also when the night stops. A unit already claimed
        stops the night: the coordinator never hands one unit to two workers, so only a claim
        this run failed to release can be there."""
        record = {"run": self.config.run_id, "worker": self.worker, "exe": pick.exe,
                  "unit": pick.unit,
                  "function": f"func_{pick.start:08X}", "start": f"0x{pick.start:08X}",
                  "kind": self.config.session, "pass": self._pass(pick),
                  "model": self._model(pick),
                  "claimed_at": datetime.now(UTC).isoformat(timespec="seconds")}  # fmt: skip
        if not self.claims.take(record):
            shown = self.claims.path(pick.exe, pick.unit).relative_to(self.repo).as_posix()
            raise _Stop(ERROR, f"{pick.exe}/{pick.unit} is already claimed ({shown})")
        try:
            yield
        finally:
            self.claims.release(pick.exe, pick.unit)
        self._retry_deferred(own=(pick.exe, pick.unit))  # 07-34: a claim was released

    def _reset_live(self) -> None:
        if self.live is None:
            return
        try:
            self._reset(self.live)
        except Exception:  # noqa: BLE001 - the stop names the first failure
            pass

    def _attempt(self, pick: Pick, n: int) -> str | None:
        """Launch until one session counts (its outcome), a LIMIT session matches (MATCHED), or
        the first launch and TRANSIENT_RETRIES retries were all transient (ABORTED, an abort
        record with retries = TRANSIENT_RETRIES; D-08, fix round 1 minor 6). Each transient
        launch spends its night-cap slot and a retry reserves a new one (07-26 fix round 1);
        when the cap leaves none, the attempt is aborted with the retries it made."""
        transient = 0
        while True:
            self._halt_if_stopping()
            probe = self.pause.wait_to_launch()  # D-07: no launch while the pause holds
            claim = self._claim(pick, n)
            session = self._launch(claim)
            if self.stop.is_set():  # 07-21: another worker stopped the night: land nothing
                self._reset(session)
                raise _Halt()
            disposition = session.disposition
            if disposition is Disposition.LIMIT:
                self._after_session(session)
                matched = self._salvage(session)
                self._limited(pick, n, probe)
                if matched:
                    return MATCHED
                continue
            self.pause.on_clear(probe)
            if disposition is Disposition.TRANSIENT:
                self._reset(session)
                self._spend()
                transient += 1
                if transient > TRANSIENT_RETRIES or not self._reserve():
                    self._halt_if_stopping()
                    self._record_abort(claim, transient - 1)
                    return ABORTED
                continue
            self._after_session(session)
            return self._counted(session)

    def _claim(self, pick: Pick, n: int) -> _Claim:
        """07-30 (D-09, D-25): attempt `n` of the function's pass tonight, on the model
        session.model_for_pass gives that pass (Opus for passes 1 and 2, Fable from pass 3) and
        with that model's budget."""
        pass_n = self._pass(pick)
        model = self._model(pick)
        return _Claim(pick, self.config.run_id, self.repo, n, pass_n=pass_n, model=model,
                      budget_usd=self.config.budget_for(model),
                      session=self.config.session)  # fmt: skip

    def _limited(self, pick: Pick, n: int, probe: bool) -> None:
        """A LIMIT session (D-07): the worker that starts or renews the shared pause waits its
        backoff, then the next launch of any worker is the probe; under a pause another worker
        started, this worker just waits at its next launch."""
        limited = self.pause.on_limit(probe)
        if limited is None:
            self.deps.say(f"{self._label(pick, n)}: usage limit, the night is already paused")
            return
        seconds, streak = limited
        self.deps.say(f"{self._label(pick, n)}: usage limit, next launch in {seconds} s")
        try:
            self._record_limit(seconds, streak)  # 07-23 (DEC-06): every wait is recorded
            self._nap(seconds)
        finally:
            self.pause.backoff_done()

    def _nap(self, seconds: float) -> None:
        """The backoff wait. With the real clock it ends early when the night stops, so a stop
        or an interrupt never waits out a 300 s poll; an injected `Deps.sleep` (the tests' fake
        clock) is called as it is."""
        if self.deps.sleep is time.sleep:
            self.stop.wait(seconds)
        else:
            self.deps.sleep(seconds)

    # --- one session ---

    def _fresh_dir(self, claim: _Claim) -> None:
        """Move an earlier launch's directory aside, so this session starts with no files."""
        directory = claim.attempt_dir
        if directory.exists():
            k = 1
            while (aside := directory.with_name(f"{directory.name}-uncounted-{k}")).exists():
                k += 1
            directory.rename(aside)
        directory.mkdir(parents=True)

    def _make_view(self, claim: _Claim) -> tuple[str, bool]:
        """D-24: build/driver/<run>/<exe>/<func>/attempt-<n>/view/ from HEAD, never the
        worktree: HEAD's tracked src/, include/ and config/ (those HEAD has) through
        `git archive`, extracted with tarfile's `data` filter (no link, device or path that
        leaves the view). include/ always exists (a view without it would compile against the
        committed headers, 07-11 as built). The claimed unit is HEAD's file, or the scaffold
        written into the view. The commit is recorded in <attempt dir>/view-head.txt (F34).
        Returns (that commit, whether the unit was scaffolded)."""
        head = _git_ok(self._git, ["rev-parse", "--verify", "HEAD^{commit}"]).decode().strip()
        listed = _git_ok(self._git, ["ls-tree", "-z", "--name-only", head, "--", *VIEW_TREES])
        trees = [name for name in listed.decode("utf-8", "surrogateescape").split("\0")
                 if name in VIEW_TREES]  # fmt: skip
        view = claim.view_root
        view.mkdir()
        if trees:
            archive = _git_ok(self._git, ["archive", "--format=tar", head, "--", *trees])
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
                tar.extractall(view, filter="data")
        (view / "include").mkdir(exist_ok=True)
        write_atomic(claim.attempt_dir / VIEW_HEAD, f"{head}\n".encode("ascii"))
        unit = claim.view_unit
        if unit.is_file() and not _is_link(unit):
            return head, False
        if os.path.lexists(unit):
            raise DriverError(f"{claim.view_unit_rel} is not a regular file at HEAD")
        unit.parent.mkdir(parents=True, exist_ok=True)
        self.deps.scaffold(claim.pick, unit)
        if not unit.is_file():
            raise DriverError(f"scaffold wrote no {claim.view_unit_rel}")
        return head, True

    def _land(self, session: _Session) -> None:
        """The landing section's first step (D-06, D-24): the only writer of src/. The view
        unit's bytes are copied to src/<exe>/<unit>.c, so the lint and the unchanged gate see
        src/ equal to HEAD but for that one unit; `_reset` puts back just that unit. 07-34
        (D-19, CONTEXT default): first every rename committed since the view's HEAD
        (`_renames_since`) is rewritten in the view unit, so a session that started before a
        rename lands under the new names."""
        claim = session.claim
        data = self._view_bytes(session)
        target = self.repo / claim.unit_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        self.landed = claim.unit_rel
        self.landed_bytes = data
        write_atomic(target, data)

    def _view_bytes(self, session: _Session) -> bytes:
        """The bytes the landing would copy: the view unit with every rename committed since
        the view's HEAD rewritten in (07-34), written back to the view when that changed it.
        A view unit that is a link or no regular file is a DriverError: nothing lands."""
        claim = session.claim
        source = claim.view_unit
        if _is_link(source) or not source.is_file():
            raise DriverError(f"{claim.view_unit_rel} is not a regular file: nothing landed")
        data = source.read_bytes()
        mapping = self._renames_since(session.view_head).get(claim.pick.exe, {})
        rewritten = _rewrite(data, mapping)
        if rewritten != data:
            write_atomic(source, rewritten)
        return rewritten

    def _snapshot(self) -> _Snapshot:
        """F3: each `git status` path with its entry, content hash and bytes, plus the pinned
        paths git cannot see (security ruling)."""
        raw = _git_ok(self._git, ["status", "--porcelain=v1", "--untracked-files=all", "-z"])
        entries = parse_status(raw)
        data = {p: b for p in entries if (b := _read(self.repo / p)) is not None}
        status = {p: (code, _sha256(data.get(p))) for p, code in entries.items()}
        return _Snapshot(status, data, self._pinned_state(), self._fingerprint())

    def _pinned_state(self) -> dict[str, bytes | None]:
        return {name: _read(self._pinned_path(name)) for name in self._pinned_names()}

    def _fingerprint(self) -> dict[str, tuple[int, int]]:
        """Security ruling (third pass, widened in fix round 1): (size, mtime_ns) of every file
        in .venv, in every gitignored tree under .claude/ but .claude/worktrees/, and in every
        __pycache__ of the checkout outside build/, .venv and .git; no contents are read."""
        found: dict[str, tuple[int, int]] = {}
        for directory, names in _walk(self.repo / _VENV):  # fix round 1 minor 2: all of .venv
            self._print_files(found, directory, names)
        worktrees = [self.repo / _WORKTREES]  # git may report .claude/ itself as one entry
        for root in self._ignored_claude():
            if root.is_dir() and not _is_link(root):
                for directory, names in _walk(root, prune=worktrees):
                    self._print_files(found, directory, names)
            elif root.is_file() or _is_link(root):
                self._print_files(found, root.parent, [root.name])
        for directory, names in _walk(self.repo, skip_top=_NOT_FINGERPRINTED):
            if directory.name == _PYCACHE:
                self._print_files(found, directory, names)
        return found

    def _ignored_claude(self) -> list[Path]:
        """Every gitignored file or tree under .claude/ but .claude/worktrees/ (fix round 1
        minor 2: GSD's hooks, gsd-core and the like)."""
        args = ["ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory"]
        raw = _git_ok(self._git, [*args, "--", _CLAUDE])
        names = [n.rstrip("/") for n in raw.decode("utf-8", "surrogateescape").split("\0") if n]
        return [self.repo / n for n in names
                if n != _WORKTREES and not n.startswith(_WORKTREES + "/")]  # fmt: skip

    def _print_files(self, found: dict, directory: Path, names: Sequence[str]) -> None:
        for name in names:
            path = directory / name
            try:
                st = os.lstat(path)
            except OSError:
                continue
            found[path.relative_to(self.repo).as_posix()] = (st.st_size, st.st_mtime_ns)

    def _git_dir(self) -> Path:
        """The checkout's common git directory (.git; a worktree's shared one)."""
        if self.git_dir is None:
            raw = _git_ok(self._git, ["rev-parse", "--git-common-dir"]).decode().strip()
            path = Path(raw)
            self.git_dir = path if path.is_absolute() else self.repo / path
        return self.git_dir

    def _pinned_path(self, name: str) -> Path:
        if name.startswith(_GIT_PREFIX):
            return self._git_dir() / name[len(_GIT_PREFIX) :]
        return self.repo / name

    def _pinned_names(self) -> list[str]:
        """Security ruling: the paths outside git's view whose change the audit must see:
        .git/config, .git/info/exclude and .git/info/attributes, every file under .git/hooks/
        and .githooks/, the two Claude settings files, the venv's pyvenv.cfg, every .pth under
        its site-packages and every sitecustomize.py/usercustomize.py under it."""
        hooks_dir = self._git_dir() / "hooks"
        names = [*(_GIT_PREFIX + name for name in _GIT_PINNED), *_PINNED_FILES]
        names += [_GIT_PREFIX + "hooks/" + p.relative_to(hooks_dir).as_posix()
                  for p in _files(hooks_dir)]  # fmt: skip
        names += [p.relative_to(self.repo).as_posix() for p in _files(self.repo / ".githooks")]
        for pattern in _PTH_GLOBS:
            names += [p.relative_to(self.repo).as_posix() for p in self.repo.glob(pattern)]
        for directory, files in _walk(self.repo / _VENV):  # third pass: *customize.py
            names += [(directory / f).relative_to(self.repo).as_posix()
                      for f in files if f in _CUSTOMIZE]  # fmt: skip
        return sorted(set(names))

    def _tracked(self) -> frozenset[str]:
        raw = _git_ok(self._git, ["ls-files", "-z"])
        names = raw.decode("utf-8", "surrogateescape").split("\0")
        return frozenset(name.casefold() for name in names if name)

    def _allowed(self, claim: _Claim, tracked: frozenset[str]) -> Callable[[str], bool]:
        def is_tracked(rel: str) -> bool:
            return rel.replace("\\", "/").casefold() in tracked

        def allowed(rel: str) -> bool:  # view mode (07-13, D-24): the hook's own allowlist
            return hooks.matching_write_allowed(rel, claim=claim.target, notes=claim.notes_rel,
                                                tracked=is_tracked, unit_file=claim.view_unit_rel,
                                                proposals=claim.proposals_rel)  # fmt: skip

        return allowed

    def _launch(self, claim: _Claim) -> _Session:
        self._fresh_dir(claim)
        view_head, scaffolded = self._make_view(claim)
        unit_before = claim.view_unit.read_bytes()
        view_hashes = self._view_hashes(claim)
        pack = self.deps.pack(claim.pick, claim.attempt_dir, claim.view_root / attempt.VIEW_SRC)
        prompt, skill = self._prompt(claim)
        base =self.config.base_env if self.config.base_env is not None else os.environ
        with self.gate_lock:  # 07-21: never while another worker's landing has src/ dirty
            before = self._snapshot()
            drift = self._pinned_drift(before)
            if drift:  # fix round 1 (C1): another live session's stray; nothing launches
                session = _Session(claim, None, pack, 0.0, (), scaffolded, unit_before, before,
                                   tuple(drift), (), view_head, before.status,
                                   view_hashes)  # fmt: skip
                self._guardrail(session, drift, record=False, extra=[
                    f"pinned paths differed from the night's baseline at the launch of "
                    f"{claim.target}: {_listed(drift)}"])  # fmt: skip
        start = self.deps.clock()
        result = None
        try:
            argv = self.deps.argv(prompt, model=claim.model, max_budget_usd=claim.budget_usd,
                                  max_turns=self.config.max_turns, **skill)  # fmt: skip
            result = self.deps.session(argv, cwd=self.repo,
                                       env=claim.env(base),
                                       transcript=claim.attempt_dir / TRANSCRIPT,
                                       timeout_s=self.config.wall_clock_s,
                                       on_start=self._on_start, on_end=self._on_end)  # fmt: skip
        except BaseException as exc:
            # Third pass: contain what the session left before the stop. Minor 8: an interrupt
            # is contained the same way, then re-raised for run() to record. Minor 1: nothing
            # is measured until the attempt's containers are gone.
            note = self._remove_containers(claim)
            with self.gate_lock:
                session = self._measure(claim, None, pack, 0.0, before, scaffolded,
                                        unit_before, view_head, view_hashes)  # fmt: skip
                stray = self._strays(session)
                contained = f"; {self._contain_and_reset(session, stray)}" if stray else ""
                contained += f"; {note}" if note else ""
                if not stray:
                    self._reset(session)
            if not isinstance(exc, Exception):
                self.interrupted = f" during a session{contained}"
                raise
            why = f"the session raised {type(exc).__name__}: {exc}{contained}"
            raise _Stop(ERROR, why) from exc
        note = self._remove_containers(claim)
        seconds = self.deps.clock() - start
        # 07-21: the audit runs under the gate lock, so it never meets another worker's landing
        # half done (its unit in src/, its gate writing status.csv): git can see only HEAD and
        # the driver's own bytes (D-24 a).
        with self.gate_lock:
            session = self._measure(claim, result, pack, seconds, before, scaffolded,
                                    unit_before, view_head, view_hashes)  # fmt: skip
            self.live = session
            try:
                self._audit(session)
            except _Stop as stop:
                if note:
                    raise _Stop(stop.reason, f"{stop.detail}; {note}") from None
                raise
        if self.stop.is_set():  # 07-21 stop-all: audited and contained; nothing lands now
            self._reset(session)
            raise _Halt(f"{claim.target}: {note}" if note else "")
        if note:  # S1: the night stops after the audit and containment ran
            self._reset(session)
            if session.counted:  # fix round 2 minor 4: the attempt is recorded like any stop
                self._count()
                summary = read_checks(claim.attempt_dir)
                self._record_attempt(session, GAVE_UP, TOOL, summary)
            raise _Stop(TOOL, note)
        if session.disposition is Disposition.STOP:
            self._reset(session)
            raise _Stop(STOP_SIGNAL, "the session's stream carries a D-08 STOP signal")
        self._check_init(session)
        return session

    def _prompt(self, claim: _Claim) -> tuple[str, dict[str, str]]:
        """The session's /goal and the extra Deps.argv keywords of its kind: a matching
        session's goal_prompt and the default skill (watcom-decomp); a readability session's
        readability_goal and READABILITY_SKILL (07-38, D-18)."""
        if claim.session == READABILITY:
            goal = readability_goal(claim.pick.unit, claim.pick.exe,
                                    unit_path=claim.view_unit_rel)  # fmt: skip
            return goal, {"skill": READABILITY_SKILL}
        return goal_prompt(claim.function, claim.pick.unit, claim.pick.exe,
                           unit_path=claim.view_unit_rel), {}  # fmt: skip

    def _remove_containers(self, claim: _Claim) -> str:
        """Fix round 1 S1: remove the attempt's containers; a failure never gates the audit and
        containment that follow, it is only returned as a note for the record."""
        try:
            self.deps.remove_containers(attempt.container_prefix(claim.attempt_dir))
        except Exception as exc:  # noqa: BLE001 - recorded, and the night stops after the audit
            return f"containers not removed: {type(exc).__name__}: {exc}"
        return ""

    def _measure(self, claim, result, pack, seconds, before, scaffolded, unit_before,
                 view_head, view_hashes) -> _Session:
        after = self._snapshot()
        changed = tuple(sorted(p for p in before.status.keys() | after.status.keys()
                               if before.status.get(p) != after.status.get(p)))  # fmt: skip
        base = self._pinned_baseline(before)  # C1: the night's, not this launch's
        pinned = tuple(sorted(n for n in base.keys() | after.pinned.keys()
                              if base.get(n) != after.pinned.get(n)))  # fmt: skip
        prints = tuple(sorted(n for n in before.prints.keys() | after.prints.keys()
                              if before.prints.get(n) != after.prints.get(n)))  # fmt: skip
        return _Session(claim, result, pack, seconds, changed, scaffolded, unit_before, before,
                        pinned, prints, view_head, after.status, view_hashes)  # fmt: skip

    def _strays(self, session: _Session) -> list[str]:
        """D-24's two invariants, plus the Phase 6 checks (D-17, F3, security rulings): (a)
        every path git can see equals HEAD, or holds the bytes the driver last wrote (the
        ledger), unstaged; (b) every file of the session's view but its unit and view/build/
        is as it was at launch, and the unit is a regular file; every pinned path outside
        git's view and every fingerprinted file is unchanged; every write tool the transcript
        names passed the hook's view-mode allowlist."""
        allowed = self._allowed(session.claim, self._tracked())
        stray = [p for p in self._unexplained(session.after) if not allowed(p)]
        stray += [name for name in self._view_changes(session) if name not in stray]
        stray += [name for name in session.pinned_changed if name not in stray]
        stray += [name for name in session.print_changed if name not in stray]
        raws = _write_targets(session.events)
        for raw, rels in zip(raws, transcript_paths(session.events, self.repo), strict=True):
            if rels is None or not all(allowed(rel) for rel in rels):
                stray.append(f"{raw}{_TRANSCRIPT_MARK}")
        return stray

    def _head_bytes(self, rel: str) -> bytes | None:
        """HEAD's blob of `rel`, or None when HEAD has none (or git cannot show it)."""
        done = self._git(["cat-file", "blob", f"HEAD:{rel}"])
        return done.stdout if done.returncode == 0 else None

    def _breach(self, rel: str, good: bytes | None, *, ledgered: bool = True) -> str:
        """Fix round 1: `rel` changed since the driver last wrote it (or since HEAD, before its
        first write). The file is kept in the quarantine (moved when no bytes are expected),
        put back to `good`, the attempt in progress is reset, and nothing is committed this
        night (sticky, as any breach). Returns the detail for the STOPPED record."""
        self.breached = True
        done = _Contained()
        path = self.repo / rel
        try:
            if path.is_file() or _is_link(path):
                self._keep(done, rel, path, move=good is None)
            if good is not None and not self._restore_bytes(rel, path, good):
                done.not_restored.append(rel)
        except Exception as exc:  # noqa: BLE001 - named in the record
            done.refused.append(f"{rel}: {type(exc).__name__}: {exc}")
        if ledgered:
            self.ledger.set(rel, good)
        if self.live is not None:
            try:
                self._reset(self.live)
            except Exception as exc:  # noqa: BLE001 - named in the record
                done.refused.append(f"the attempt reset failed: {type(exc).__name__}: {exc}")
        detail = (f"{rel} does not hold the bytes the driver last wrote (D-24 ledger breach); "
                  f"quarantined: {_listed(done.quarantined)}")  # fmt: skip
        if done.not_restored:
            detail += f"; not restored: {_listed(done.not_restored)}"
        if done.refused:
            detail += "; " + "; ".join(done.refused)
        return detail

    def _guard(self, *rels: str) -> None:
        """Fix round 1: right before a driver write, each driver-owned file must still hold the
        bytes the driver last wrote (or HEAD's); otherwise the night stops as a breach."""
        for rel in rels:
            if not self.ledger.holds(rel):
                raise _Stop(GUARDRAIL, self._breach(rel, self.ledger.expected(rel)))

    def _ledger_breaches(self) -> list[str]:
        """At the end of the night, before the chore commit: every output that commit may carry
        (the log, both status.csv files, the feed; fix round 2) and every other ledgered file
        must hold the driver's bytes, or HEAD's when the driver never wrote it tonight. Each
        one that does not is contained (fix round 1)."""
        rels = sorted({*self._outputs(), *self.ledger.paths()})
        return [self._breach(rel, self.ledger.expected(rel))
                for rel in rels if not self.ledger.holds(rel)]  # fmt: skip

    def _verify_landing(self, session: _Session) -> None:
        """Fix round 1: right before the match commit's `git add`, status.csv, the feed and the
        log hold the driver's bytes and src/ holds the unit it landed. 07-21: after another
        worker's breach (J2: sticky) nothing is committed any more; and (07-21 fix round 1,
        the review's open point) every other path git can see equals HEAD or holds the
        driver's own bytes, so no live session's write rides along with this landing."""
        claim = session.claim
        if self.breached:
            raise _Breach("another worker's breach stopped the night: nothing is committed (J2)")
        for rel in (claim.status_rel, FEED, ATTEMPT_LOG.as_posix()):
            if not self.ledger.holds(rel):
                raise _Breach(self._breach(rel, self.ledger.expected(rel)))
        unit = self.repo / claim.unit_rel
        if _is_link(unit) or _read(unit) != self.landed_bytes:
            raise _Breach(self._breach(claim.unit_rel, self.landed_bytes, ledgered=False))
        raw = _git_ok(self._git, ["status", "--porcelain=v1", "--untracked-files=all", "-z"])
        status = {path: (code, None) for path, code in parse_status(raw).items()}
        others = [p for p in self._unexplained(status) if p != claim.unit_rel]
        if others:
            self.breached = True
            done = self._contain(session, others)
            raise _Breach(f"paths changed besides the landing at the match commit: "
                          f"{_listed(others)}; {self._contained_text(done)}")  # fmt: skip

    def _contained_text(self, done: _Contained) -> str:
        """What one containment did, for a STOPPED record."""
        text = f"restored: {_listed(done.restored)}; quarantined: {_listed(done.quarantined)}"
        for label, items in (("not contained", done.not_contained),
                             ("not restored", done.not_restored),
                             ("could not unstage", done.unstage_failed)):  # fmt: skip
            if items:
                text += f"; {label}: {_listed(items)}"
        return "; ".join([text, *done.refused])

    def _verify_commit(self, claim: _Claim, paths: Sequence[str], old: str, subject: str
                       ) -> None:  # fmt: skip
        """07-21 fix round 1 (I1): `git commit -- <paths>` reads the worktree again after
        `_verify_landing`, so a live session's write in between would be committed. Each
        committed blob must be the unit the driver landed or the driver's ledgered bytes, as
        git stores them (fix round 2, N1: object ids hashed with the path's attributes, so an
        eol rule never reads as a breach). On a difference the driver moves HEAD back off its
        own commit (`git update-ref HEAD <old> <new>`), contains each path and raises _Breach,
        which the caller's `_undo_match` takes from there.

        Fix round 2 (N2): HEAD is only ever moved back when it is the driver's own commit, made
        on the HEAD it read: one parent, `old`, and the driver's subject. Otherwise a foreign
        commit came in; HEAD stays, the record names it and `_Kept` stops the night. N4: a
        failing check, or a failed move, also leaves the commit, and nothing is put back
        under it (`_Kept`)."""
        try:
            new = _git_ok(self._git, ["rev-parse", "--verify", "HEAD^{commit}"]).decode().strip()
            foreign = self._foreign_commits(old, new, subject)
            wanted = {rel: (self.landed_bytes if rel == claim.unit_rel
                            else self.ledger.expected(rel)) for rel in paths}  # fmt: skip
            bad = [rel for rel, want in wanted.items() if not self._committed_as(new, rel, want)]
        except Exception as exc:  # noqa: BLE001 - N4: the commit exists; named, nothing undone
            raise _Kept(f"the match commit was made but could not be checked: "
                        f"{type(exc).__name__}: {exc}; HEAD was not moved and nothing was "
                        f"put back under the commit") from exc  # fmt: skip
        if not bad and not foreign:
            return
        notes, kept = [], bool(foreign)
        if foreign:
            notes.append(f"commits the driver did not make came in during its match commit: "
                         f"{_listed(foreign)}; HEAD left at {new[:12]}, "
                         f"not moved back")  # fmt: skip
        if bad:
            notes.append(f"the match commit holds bytes the driver did not write: {_listed(bad)}")
        if bad and not foreign:
            try:
                _git_ok(self._git, ["update-ref", "-m", "reverseapoc drive: undo a tampered match",
                                    "HEAD", old, new])  # fmt: skip
                notes.append(f"HEAD moved back to {old[:12]}")
            except Exception as exc:  # noqa: BLE001 - named; the commit then stays (N4)
                notes.append(f"HEAD could not be moved back: {type(exc).__name__}: {exc}")
                kept = True
        for rel in bad:
            notes.append(self._breach(rel, wanted[rel], ledgered=rel != claim.unit_rel))
        raise (_Kept if kept else _Breach)("; ".join(notes))

    def _foreign_commits(self, old: str, new: str, subject: str) -> list[str]:
        """N2: the commits from `old` to HEAD (`new`) the driver did not make, as "<sha> <subject>".
        Empty when HEAD is the driver's own commit on `old`: exactly one parent, `old`, and the
        driver's subject."""
        parents = _git_ok(self._git, ["rev-list", "--parents", "-n", "1", new]).decode().split()
        own = _git_ok(self._git, ["log", "-1", "--format=%s", new]).decode().strip()
        if parents[1:] == [old] and own == subject:
            return []
        out = _git_ok(self._git, ["log", "--format=%H %s", f"{old}..{new}"]).decode()
        found = [(line[:12], line.partition(" ")[2]) for line in out.splitlines() if line]
        foreign = [f"{sha} {text}" for sha, text in found if text != subject]
        listed = [f"{sha} {text}" for sha, text in found]
        return foreign or listed or [f"HEAD {new[:12]} does not descend from {old[:12]}"]

    def _committed_as(self, commit: str, rel: str, data: bytes | None) -> bool:
        """N1: whether `commit` holds `rel` as git would store `data` there (None: no such
        path). `data` is hashed with `hash-object --path=<rel> --stdin`, which applies the same
        attributes (eol, filters) as the commit did; the object ids are compared."""
        done = self._git([LITERAL, "rev-parse", "--verify", "--quiet", f"{commit}:{rel}"])
        if data is None or done.returncode != 0:
            return data is None and done.returncode != 0
        hashed = self._git([LITERAL, "hash-object", f"--path={rel}", "--stdin"], input=data)
        return _git_stdout(hashed, ["hash-object", rel]).strip() == done.stdout.strip()

    def _unexplained(self, status: Mapping[str, tuple[str, str | None]]) -> list[str]:
        """Invariant (a): each path of `status` (git status after the session) or of the
        ledger that neither equals HEAD nor holds, unstaged, the bytes the driver wrote."""
        out = []
        for path in sorted(status.keys() | set(self.ledger.paths())):
            code = status.get(path, ("  ", None))[0]
            if self.ledger.knows(path):
                if self.ledger.matches(path) and code[0] in (" ", "?"):
                    continue
            elif path not in status:
                continue
            out.append(path)
        return out

    def _view_hashes(self, claim: _Claim) -> dict[str, str]:
        """Invariant (b): every file of the view but its unit and view/build/ (the wrapper's
        objects and logs), repo-relative, with its content hash; a link is recorded by its
        target, never followed."""
        root = claim.view_root
        unit = claim.view_unit
        found: dict[str, str] = {}
        for directory, names in _walk(root, skip_top=(attempt.VIEW_BUILD,)):
            for name in names:
                path = directory / name
                if path == unit:
                    continue
                rel = path.relative_to(self.repo).as_posix()
                found[rel] = (f"link:{os.readlink(path)}" if _is_link(path)
                              else _sha256(_read(path)) or "unreadable")  # fmt: skip
        return found

    def _view_changes(self, session: _Session) -> list[str]:
        """The view files added, removed or changed since launch, and the view unit when it
        is no longer a regular file (a link, a directory or gone)."""
        claim = session.claim
        now = self._view_hashes(claim)
        launch = session.view_hashes
        changed = sorted(n for n in launch.keys() | now.keys() if launch.get(n) != now.get(n))
        unit = claim.view_unit
        if _is_link(unit) or not unit.is_file():
            changed.append(claim.view_unit_rel)
        return changed

    def _audit(self, session: _Session) -> None:
        stray = self._strays(session)
        if not stray:
            return
        # 07-21 stop-all: a session the stop killed is contained like any other, but neither
        # counted nor recorded (the first failure writes the night's STOPPED record).
        counted = session.counted and not self.stop.is_set()
        if counted:
            self._count()
        self._guardrail(session, stray, record=counted)

    def _guardrail(
        self, session: _Session, stray: Sequence[str], *, record: bool, extra: Sequence[str] = ()
    ) -> None:
        """Security ruling: a breach never leaves the strays in place and never deletes one.
        Each stray file is copied (tracked, or pinned with earlier bytes) or moved (new) into
        build/driver/<run>/quarantine/<path>, then put back as it was before the session; the
        attempt is reset as usual and the STOPPED record lists every path."""
        detail = "; ".join([self._contain_and_reset(session, stray), *extra])
        if record:
            self._record_attempt(session, GAVE_UP, GUARDRAIL,
                                 read_checks(session.claim.attempt_dir))  # fmt: skip
        raise _Stop(GUARDRAIL, detail)

    def _contain_and_reset(self, session: _Session, stray: Sequence[str]) -> str:
        """Contain the strays, reset the attempt, take the pinned snapshot and the fingerprint
        again, and describe all of it. A refused quarantine write (a link) writes nothing more
        and is named."""
        self.breached = True  # fix round 2 J2: sticky, whatever the final reason
        files = [s for s in stray if not s.endswith(_TRANSCRIPT_MARK)]
        done = self._contain(session, files)
        try:
            self._reset(session)
        except Exception as exc:  # noqa: BLE001 - named in the record
            done.refused.append(f"the attempt reset failed: {type(exc).__name__}: {exc}")
        detail = (f"stray paths: {_listed(list(stray))}; restored: {_listed(done.restored)}"
                  f"; quarantined: {_listed(done.quarantined)}")  # fmt: skip
        if done.not_contained:
            detail += f"; not contained: {_listed(done.not_contained)}"
        if done.not_restored:
            detail += f"; not restored: {_listed(done.not_restored)}"
        if done.unstage_failed:
            detail += f"; restored; could not unstage: {_listed(done.unstage_failed)}"
        if done.refused:
            detail += "; " + "; ".join(done.refused)
        try:
            still = self._still_changed(session)
        except Exception as exc:  # noqa: BLE001 - named in the record
            still = [f"<not measured: {type(exc).__name__}: {exc}>"]
        return f"{detail}; still changed after containment: {_listed(still)}" if still else detail

    def _still_changed(self, session: _Session) -> list[str]:
        """Third pass: the pinned paths and fingerprinted files that still differ from the
        pre-session snapshot once containment is done (a pinned file restored from its bytes
        has a new mtime, so the fingerprint skips pinned names)."""
        before = session.before
        base = self._pinned_baseline(before)  # C1
        pinned = self._pinned_state()
        prints = self._fingerprint()
        still = [n for n in sorted(base.keys() | pinned.keys())
                 if base.get(n) != pinned.get(n)]  # fmt: skip
        still += [n for n in sorted(before.prints.keys() | prints.keys())
                  if before.prints.get(n) != prints.get(n) and n not in pinned]  # fmt: skip
        return still

    def _quarantine_root(self) -> Path:
        return self.repo.joinpath(DRIVER_DIR, self.config.run_id, QUARANTINE)

    def _safe_dir(self, directory: Path) -> None:
        """Create `directory` component by component below the checkout, refusing (STOP,
        nothing written) any component that is a symlink, a junction or a reparse point, and
        any directory that does not resolve inside the quarantine root."""
        rel = directory.relative_to(self.repo)
        current = self.repo
        for part in rel.parts:
            current = current / part
            if not os.path.lexists(current):
                current.mkdir()
            if _is_link(current) or not current.is_dir():
                shown = current.relative_to(self.repo).as_posix()
                raise _Stop(GUARDRAIL, f"quarantine path {shown} is a link, a junction or not a "
                                       "directory: nothing written there")  # fmt: skip
        root = self._quarantine_root()
        if directory != root and not directory.resolve().is_relative_to(root.resolve()):
            raise _Stop(GUARDRAIL, f"{directory} resolves outside the quarantine: nothing written")

    def _quarantine(self, name: str, path: Path, *, move: bool) -> str:
        """Copy (or move: copy, then remove the source) `path` to
        build/driver/<run>/quarantine/<name> (third pass: no link followed, O_EXCL, never
        overwrites). A link left by the session is kept as a note naming its target."""
        target = self._quarantine_root().joinpath(*name.split("/"))
        self._safe_dir(target.parent)
        if _is_link(path):
            data = f"a link to {os.readlink(path)}\n".encode("utf-8", "surrogateescape")
            target = target.with_name(target.name + ".link")
        else:
            data = path.read_bytes()
        stem, k = target.name, 0
        while True:
            try:
                _write_new(target, data)
                break
            except FileExistsError:
                k += 1
                target = target.with_name(f"{stem}.{k}")
        if move:
            path.unlink()
        return f"{name} -> {target.relative_to(self.repo).as_posix()}"

    def _keep(self, done: _Contained, name: str, path: Path, *, move: bool) -> bool:
        """Quarantine one file; a refusal is recorded for that file alone (fourth pass)."""
        try:
            done.quarantined.append(self._quarantine(name, path, move=move))
            return True
        except _Stop as stop:
            done.refused.append(f"refused {name}: {stop.detail}")
            return False

    def _contain(self, session: _Session, files: Sequence[str]) -> _Contained:
        """Put each stray path back as it was before the session, keeping what the session left
        in quarantine. Tracked: copied, then back to HEAD, or to the driver's own pre-session
        bytes when the driver had changed it; pinned: copied, then back to the earlier bytes;
        new (untracked, or a pinned or fingerprinted file the session created): moved out.
        Fourth pass: each file is handled alone, and restoring never depends on the copy; a new
        file whose quarantine is refused stays in place, named "not contained". 07-13: a
        driver-owned file goes back to the bytes the driver last wrote (the ledger)."""
        done = _Contained()
        try:
            tracked = self._tracked()
        except Exception as exc:  # noqa: BLE001 - every file is then judged untracked, named
            done.refused.append(f"git ls-files failed: {type(exc).__name__}: {exc}")
            tracked = frozenset()
        for name in files:
            try:  # fix round 2 J2: one failing file never stops the others
                self._contain_one(done, session, name, tracked)
            except Exception as exc:  # noqa: BLE001 - named in the record
                done.not_restored.append(f"{name} ({type(exc).__name__}: {exc})")
        return done

    def _contain_one(self, done: _Contained, session: _Session, name: str,
                     tracked: frozenset[str]) -> None:  # fmt: skip
        """Contain one stray (see _contain)."""
        before = session.before
        # 07-21 fix round 2 (N3): once the night's baseline is set (the night starts clean),
        # every pinned change goes back to it, tracked or not; a launch snapshot may hold a
        # stray. Outside a night an untracked pinned name keeps its snapshot bytes as before.
        pinned = name in session.pinned_changed and (
            self.pinned_base is not None or name.casefold() not in tracked)
        path = self._pinned_path(name) if pinned else self.repo / name
        if pinned:  # C1: back to the night's baseline, never a launch snapshot's stray
            earlier = self._pinned_baseline(before).get(name)
        elif self.ledger.knows(name):  # 07-13: the driver's own file, back to its bytes
            earlier = self.ledger.bytes_of(name)
        else:
            earlier = before.data.get(name)
        # A fingerprinted file has no saved bytes: a new one moves out, a changed one is
        # copied and stays (named again under "still changed").
        changed_print = name in session.print_changed and name in before.prints
        move = earlier is None and name.casefold() not in tracked and not changed_print
        if path.is_dir() and not _is_link(path):  # minor 9: a nested repo, say
            done.not_contained.append(f"{name} (a directory)")
            return
        if path.is_file() or _is_link(path):
            if not self._keep(done, name, path, move=move) and move:
                done.not_contained.append(name)
                return
        if not pinned and name.casefold() in tracked and earlier is None:
            _git_ok(self._git, ["restore", "--source=HEAD", "--staged", "--worktree",
                                    "--", name])  # fmt: skip
            done.restored.append(name)
        elif earlier is not None:
            if not self._restore_bytes(name, path, earlier):
                done.not_restored.append(name)
                return
            if name.casefold() in tracked:
                try:
                    _git_ok(self._git, ["restore", "--staged", "--", name])
                except Exception as exc:  # noqa: BLE001 - minor 2: the bytes did come back
                    done.unstage_failed.append(f"{name} ({type(exc).__name__}: {exc})")
                    return
            done.restored.append(name)

    def _restore_bytes(self, name: str, path: Path, data: bytes) -> bool:
        """Fix round 1 minor 4: write `data` back to `path` only when no component between its
        anchor (the checkout, or the git directory for .git/ names) and its parent is a link,
        a junction or a reparse point, and the parent resolves inside the anchor. S2: a leaf
        that is a link is replaced, never followed: a directory link (a junction) is removed
        first, since os.replace cannot replace a directory; a file link is swapped out by
        write_atomic's os.replace. The quarantine already holds a note naming its target."""
        anchor = self._git_dir() if name.startswith(_GIT_PREFIX) else self.repo
        try:
            parts = path.parent.relative_to(anchor).parts
        except ValueError:
            return False
        current = anchor
        for part in parts:
            current = current / part
            if _is_link(current) or not current.is_dir():
                return False
        if not path.parent.resolve().is_relative_to(anchor.resolve()):
            return False
        if os.path.isjunction(path):
            os.rmdir(path)  # removes the junction itself, never its target
        elif _is_link(path) and path.is_dir():  # a directory symlink: the link, never its target
            if os.name == "nt":
                os.rmdir(path)  # Windows removes a directory symlink with rmdir
            else:
                os.unlink(path)
        write_atomic(path, data)
        return True

    def _check_init(self, session: _Session) -> None:
        """Pitfall 2: any problem with the init event stops the night. A session with no init is
        judged only when it produced a result (a hang or a crash before init is not). 07-30
        (D-09): the init must name the model the session asked for (streamjson's accepted IDs),
        so a Fable pass passes and a request answered by another model stops the night."""
        init = streamjson.init_event(session.events)
        if init is None and not (session.counted and not session.result.timed_out):
            return
        problems = streamjson.check_init(init, tested_major=self.config.tested_major,
                                         min_version=self.config.min_cli_version,
                                         expected_model=session.claim.model)  # fmt: skip
        if problems:
            self._reset(session)
            raise _Stop(INIT, "; ".join(problems))

    def _reset(self, session: _Session) -> None:
        """D-34, D-24: put back only the claimed unit in src/: `git restore --source=HEAD --
        <unit>` when HEAD tracks it, else delete the copy the landing section wrote. The view
        is abandoned as it is (kept for inspection). Never all of include/, never `git add -A`,
        never `git clean`. src/ is shared by every worker's gate, so this runs under the gate
        lock (07-18 fix round 1), from any caller: the landing, a TRANSIENT relaunch, a stop."""
        claim = session.claim
        unit = self.repo / claim.unit_rel
        with self.gate_lock:
            if claim.unit_rel.casefold() in self._tracked():
                _git_ok(self._git, ["restore", "--source=HEAD", "--", claim.unit_rel])
            elif self.landed == claim.unit_rel:
                unit.unlink(missing_ok=True)
            self.landed = None

    # --- judging a session ---

    def _restore_pre_gate(self) -> list[str]:
        """status.csv and the feed back to their bytes right before the gate; never the log,
        which only grows (D-27 P4). Each file is tried alone; a refused or failed restore comes
        back as a note for the record (fix round 2 minor 1: never silent)."""
        notes, breaches = [], []
        for rel, data in self.pre_gate.items():
            if data is None:
                continue
            if not self.ledger.holds(rel):  # fix round 1: changed after the gate wrote it
                breaches.append(self._breach(rel, data))
                continue
            try:
                if self._restore_bytes(rel, self.repo / rel, data):
                    self.ledger.set(rel, data)
                else:
                    notes.append(f"not restored: {rel} (refused: a link or outside the checkout)")
            except Exception as exc:  # noqa: BLE001 - named in the record
                notes.append(f"not restored: {rel} ({type(exc).__name__}: {exc})")
        self.pre_gate = {}
        if breaches:
            raise _Stop(GUARDRAIL, "; ".join([*breaches, *notes]))
        return notes

    def _tool_failure(self, session: _Session, what: str, outcome: str = GAVE_UP, *,
                      gate: GateRun | None = None) -> None:  # fmt: skip
        notes = self._restore_pre_gate()  # a gate that passed or half-wrote leaves no row behind
        self._reset(session)
        if session.counted:
            self._record_attempt(session, outcome, TOOL, read_checks(session.claim.attempt_dir),
                                 gate=gate)  # fmt: skip
        raise _Stop(TOOL, "; ".join([what, *notes]))

    def _judge(self, session: _Session) -> GateRun | None:
        """The landing section (D-24): the view unit lands in src/, then the lint, then the
        unchanged gate. None when the lint failed (the gate never runs)."""
        pick, n = session.claim.pick, session.claim.n
        self.pre_gate = {}
        self._land(session)
        lint = self.deps.lint(pick)
        if lint == EXIT_TOOL:
            self._tool_failure(session, "the C89 lint could not run (exit 2)")
        if lint != EXIT_OK:
            return None
        claim = session.claim
        self._guard(claim.status_rel, FEED)  # fix round 1: the gate starts from the driver's bytes
        self.pre_gate = {rel: self.ledger.expected(rel) for rel in (claim.status_rel, FEED)}
        before = matched_starts(self.pre_gate[claim.status_rel], pick.unit)  # `regressions`
        try:
            gate = replace(self.deps.gate(pick, n), matched_before=before)
        finally:
            self.ledger.note(claim.status_rel, FEED)  # the gate's output: the one read-back
        if gate.exit_code not in (EXIT_OK, EXIT_MISMATCH):
            self._tool_failure(session, f"gate exited {gate.exit_code}", gate=gate)
        stems = sorted(PurePosixPath(name).stem.lower() for name, _ in gate_sha1s(gate.doc))
        if gate.exit_code == EXIT_OK and stems != sorted(EXE_ORDER):  # minor 7
            self._tool_failure(session, f"gate passed but its SHA-1s name {stems}, not both of "
                                        f"{sorted(EXE_ORDER)}", gate=gate)  # fmt: skip
        return gate

    def _gate_matched(self, session: _Session, gate: GateRun | None) -> bool:
        """06-REVIEW CR-01: a gate run is a match of the claimed function only when it passed
        AND wrote a matched row for that function. A unit that already holds matched functions
        passes with the claimed one still a stub (stubs are not checked), so the exit alone
        decides nothing about the claim. Such a pass has re-hashed the unit's rows and rewritten
        the feed: those come back to their pre-gate bytes (a refused restore stops the night)."""
        if gate is None or gate.exit_code != EXIT_OK:
            return False
        if claimed_matched(gate.doc, session.claim.pick):
            return True
        notes = self._restore_pre_gate()
        if notes:
            self._tool_failure(session, "; ".join([_UNCLAIMED_PASS, *notes]), gate=gate)
        return False

    def _salvage(self, session: _Session) -> bool:
        """06-17 review: a LIMIT session keeps its work. When it changed the unit or wrote a
        header, it is judged as usual; a pass that matched the claim is a counted MATCHED.
        Otherwise it is reset. The whole landing runs under the gate lock (D-06). 07-38: a
        readability session is never salvaged (it is reset, and the relaunch redoes it; its
        proposals were applied already), so a LIMIT launch writes no readability record."""
        with self._landing(session):
            if session.has_work() and session.claim.session != READABILITY:
                gate = self._judge(session)
                if self._gate_matched(session, gate):
                    self._count()
                    self._commit_match(session, gate, read_checks(session.claim.attempt_dir))
                    return True
            self._reset(session)
            return False

    @contextmanager
    def _landing(self, session: _Session) -> Iterator[None]:
        """The gate lock for one landing section (D-06, D-27 P4). An unexpected exception
        inside it (not a _Stop: every stop path has reset already) puts the unit back while the
        lock is still held, so no other worker's whole-EXE gate sees the failed C in src/
        (07-18 fix round 1); a failing reset there is left to the stop that follows."""
        with self.gate_lock:
            try:
                yield
            except (_Stop, _Halt):
                raise
            except BaseException:
                try:
                    self._reset(session)
                except Exception:  # noqa: BLE001 - _guarded's reset retries and names it
                    pass
                raise

    def _counted(self, session: _Session) -> str:
        """A counted session's landing section, all of it under the gate lock (D-06, D-27 P4):
        the copy into src/, the lint, the gate, then the commit (or its undo) or the reset,
        `gate --partial` and the attempt record. Another worker's record waits for the landing
        decision, so F19's log truncation can only drop this landing's own MATCHED line. A
        readability session has its own landing (07-38, `_land_readability`)."""
        if session.claim.session == READABILITY:
            return self._land_readability(session)
        self._count()
        claim = session.claim
        summary = read_checks(claim.attempt_dir)
        abort = TIMEOUT if session.result.timed_out else None
        with self._landing(session):
            gate = self._judge(session)
            if self._gate_matched(session, gate):
                self._commit_match(session, gate, summary, abort)
                return MATCHED
            outcome = PARTIAL if (summary.best_percent or 0.0) > 0.0 else GAVE_UP
            if gate is None:  # a failed lint; review IN-02: PARTIAL only with a score above 0%
                abort = LINT
            self._reset(session)
            if outcome == PARTIAL and summary.best_source is not None:
                if self._partial_gate(session, summary) == EXIT_TOOL:
                    self._record_attempt(session, outcome, TOOL, summary, gate=gate)
                    raise _Stop(TOOL, "gate --partial exited 2")
            self._record_attempt(session, outcome, abort, summary, gate=gate)
            return outcome

    def _partial_gate(self, session: _Session, summary: CheckSummary) -> int | None:
        """Save the best C under best/<unit>.c and run `gate --partial` on it, passing the
        repo-relative POSIX path (F7: the gate runs in the container at /work)."""
        claim = session.claim
        source = claim.attempt_dir / summary.best_source
        if not source.is_file():
            return None
        best = claim.attempt_dir / BEST_DIR / f"{claim.pick.unit}.c"
        best.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, best)
        self._guard(claim.status_rel, FEED)  # fix round 1
        try:
            return self.deps.partial_gate(claim.pick, best.relative_to(self.repo).as_posix(),
                                          claim.n)  # fmt: skip
        finally:
            self.ledger.note(claim.status_rel, FEED)  # the partial gate's output (read back)

    # --- the readability landing (07-38; D-17, D-18, D-20, DEC-04) ---

    def _land_readability(self, session: _Session) -> str:
        """A counted readability session's landing section, all of it under the gate lock. Its
        proposals were applied already (`_after_session`, 07-34), so the view unit first takes
        the renames committed since its HEAD. Then, in order:

        - GAVE_UP when that leaves the unit as HEAD has it (nothing to land, no gate);
        - REFUSED before anything lands when the set of functions the unit defines in C or
          marks INCLUDE_ASM (by start, unitdefs.find) or its source problems differ from HEAD's:
          a readability edit never turns a stub into C (or back) or moves a definition (D-17);
        - the unit lands in src/, the C89 lint runs (owner ruling 2026-10-30: every landing
          path lints before it commits; a failing lint is REFUSED with abort_reason lint) and
          the container gate runs; a gate that fails, or passes without the unit's lowest
          matched function matched, is REFUSED: the bytes changed;
        - strict readlint on the landed unit (`run_readlint --units EXE/UNIT`, its included
          headers too). Clean: one LANDED commit of the unit, status.csv (source_sha256
          refreshed by the gate), the feed and the log (`readability_message`). Otherwise
          PARTIAL: status.csv and the feed go back to their pre-gate bytes, the view unit is
          kept under best/<unit>.c and the unit is put back.

        Every refusal puts the unit back (D-34) and writes one v2 record of its outcome; the
        record's check summary is the latest readlint-clean run (`read_checks(readability)`)."""
        self._count()
        claim = session.claim
        summary = read_checks(claim.attempt_dir, readability=True)
        abort = TIMEOUT if session.result.timed_out else None
        with self._landing(session):
            data = self._view_bytes(session)
            head = self._head_bytes(claim.unit_rel)
            if data == head:
                return self._readability_end(session, GAVE_UP, abort, summary)
            if self._defined_set(claim, data) != self._defined_set(claim, head):
                return self._readability_end(session, REFUSED, abort, summary)
            gate = self._judge(session)
            if gate is None:  # the C89 lint failed: the gate never ran
                return self._readability_end(session, REFUSED, LINT, summary)
            if not self._gate_matched(session, gate):
                return self._readability_end(session, REFUSED, abort, summary, gate=gate)
            if not self._readlint_clean(claim):
                notes = self._restore_pre_gate()  # the gate's refreshed rows are not kept
                if notes:
                    self._tool_failure(session, "; ".join(
                        ["readlint failed and the gate's rows could not be put back", *notes]),
                        PARTIAL, gate=gate)  # fmt: skip
                self._keep_best(session)
                return self._readability_end(session, PARTIAL, abort, summary, gate=gate)
            self._commit_match(session, gate, summary, abort)
            return LANDED

    def _readability_end(self, session: _Session, outcome: str, abort: str | None,
                         summary: CheckSummary, *, gate: GateRun | None = None) -> str:  # fmt: skip
        """A readability landing that commits nothing: the unit back as HEAD has it, one
        record."""
        self._reset(session)
        self._record_attempt(session, outcome, abort, summary, gate=gate)
        return outcome

    def _defined_set(self, claim: _Claim, data: bytes | None) -> tuple:
        """07-38 (D-17): what a unit's bytes define in C and mark INCLUDE_ASM, by row start
        (unitdefs.find under the EXE's current C names, so a rename moves nothing), with its
        source problems. A text that is not UTF-8 compares unequal to every other."""
        if data is None:
            return (), (), ()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return (None, _sha256(data))
        exe = claim.pick.exe
        rows = read_functions_csv(self.repo / "config" / exe / "functions.csv")
        symbols_path = self.repo / _symbols_rel(exe)
        symbols = read_symbols_csv(symbols_path) if symbols_path.is_file() else []
        unit_rows = [row for row in rows if row.unit == claim.pick.unit]
        defs = unitdefs.find(text, unit_rows, placeholders=unitdefs.placeholders(unit_rows),
                             all_names=unitdefs.c_names(rows, symbols))  # fmt: skip
        return (frozenset(defs.defined), frozenset(defs.marked),
                frozenset(defs.source_problems))  # fmt: skip

    def _keep_best(self, session: _Session) -> None:
        """PARTIAL: the view unit as it would have landed, under <attempt dir>/best/<unit>.c
        (gitignored), for the next session or the owner."""
        claim = session.claim
        best = claim.attempt_dir / BEST_DIR / f"{claim.pick.unit}.c"
        best.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(best, self.landed_bytes or b"")

    def _readlint_clean(self, claim: _Claim) -> bool:
        """Strict readlint (D-20) on the landed unit alone, as `readlint --units EXE/UNIT`
        runs it, over src/ and config/ as they are now (after the gate). Clean only when the
        unit was checked and no violation was found, in it or in a header it includes; a
        readlint error (an unreadable file or table) is not clean (fail closed)."""
        try:
            result = run_readlint([self.repo / claim.unit_rel], src_root=self.repo / "src",
                                  config_root=self.repo / "config",
                                  units=[claim.target])  # fmt: skip
        except ReadlintError:
            return False
        return result.exit_code() == EXIT_OK and claim.unit_rel in result.files_checked

    def _landing_message(self, session: _Session, gate: GateRun) -> str:
        """The commit message of a landing: D-25's match message, or a readability session's
        (07-38)."""
        claim = session.claim
        figures = dict(exe=claim.pick.exe, unit=claim.pick.unit, attempt_n=claim.n,
                       model=session.text("model"), usage=session.usage,
                       seconds=session.seconds, sha1s=gate_sha1s(gate.doc),
                       requested_model=claim.model)  # fmt: skip
        if claim.session == READABILITY:
            return readability_message(**figures)
        return commit_message(function=claim.function,
                              attempts=self.config.attempts_per_function, **figures)

    def _commit_match(self, session: _Session, gate: GateRun, summary: CheckSummary,
                      abort: str | None = None) -> None:  # fmt: skip
        """One match commit of explicit paths (D-25): the landed unit, status.csv, the feed and
        the log; a matching session adds no header (D-19). 07-38: a readability session's
        landing is the same commit with its own message and a LANDED record; only a match
        counts toward `matched`."""
        claim = session.claim
        paths = [claim.unit_rel, claim.status_rel, FEED, ATTEMPT_LOG.as_posix()]
        log_size = self.log.stat().st_size if self.log.is_file() else 0
        outcome = LANDED if claim.session == READABILITY else MATCHED
        self._record_attempt(session, outcome, abort, summary, gate=gate)
        try:
            message = self._landing_message(session, gate)
            self._verify_landing(session)
            old = _git_ok(self._git, ["rev-parse", "--verify", "HEAD^{commit}"]).decode().strip()
            self._commit_with_retry(message=message, message_file=claim.attempt_dir / COMMIT_MSG,
                                    paths=paths)  # fmt: skip
            subject = message.partition("\n")[0]
            self._verify_commit(claim, paths, old, subject)  # I1; fix round 2: N1, N2, N4
        except _Kept as exc:  # fix round 2: the commit stays, so nothing is put back under it
            self.breached = True
            raise _Stop(GUARDRAIL, exc.detail) from exc
        except _Breach as exc:  # fix round 1: never commit bytes the driver did not write
            undone = self._undo_match(session, paths, summary, exc.detail, log_size, gate=gate)
            raise _Stop(GUARDRAIL, undone) from exc
        except Exception as exc:  # fix round 2 J1: any failure, not only a DriverError
            why = f"{type(exc).__name__}: {exc}"
            undone = self._undo_match(session, paths, summary, why, log_size, gate=gate)
            raise _Stop(self.undo_reason or TOOL, undone) from exc
        except BaseException as exc:  # minor 3: an interrupt is undone, then re-raised
            undone = self._undo_match(session, paths, summary, type(exc).__name__, log_size,
                                      gate=gate)  # fmt: skip
            self.interrupted = f" during the match commit; {undone}"
            raise
        if outcome != MATCHED:
            return
        with self.cond:
            self.matched += 1
            self.cond.notify_all()

    def _undo_match(self, session: _Session, paths: Sequence[str], summary: CheckSummary,
                    why: str, log_size: int, *, gate: GateRun | None = None) -> str:  # fmt: skip
        """Fix round 1 I2, completed in fix round 2 (J1): a match commit that failed leaves no
        trace of a match. Each step is best-effort with its own note: unstage what it added,
        put status.csv and the feed back to their pre-gate bytes, truncate the log to its
        length before the MATCHED append (F19: the driver's own uncommitted MATCHED record goes,
        any record appended before it stays), reset the attempt. Then the attempt is always
        logged GAVE_UP `tool`, and the returned detail names the original error, every step
        that failed and every path still staged. The caller stops the night. 07-13 fix round
        2: a ledger breach the pre-gate restore finds is one more note (its stop reason kept in
        `undo_reason`), so the MATCHED line is still dropped and the attempt still recorded."""
        notes = [f"the match commit failed: {why}"]
        self.undo_reason = None
        try:
            _git_ok(self._git, ["restore", "--staged", "--", *paths])
        except Exception as exc:  # noqa: BLE001 - named below
            notes.append(f"could not unstage: {type(exc).__name__}: {exc}")
        try:
            notes += self._restore_pre_gate()
        except _Stop as stop:  # a breach: contained already, the undo goes on
            self.undo_reason = stop.reason
            notes.append(stop.detail)
        notes += self._drop_log_tail(log_size)
        try:
            self._reset(session)
        except Exception as exc:  # noqa: BLE001 - named below
            notes.append(f"could not reset the attempt: {type(exc).__name__}: {exc}")
        staged = self._staged()
        if staged:
            notes.append(f"still staged: {_listed(staged)}")
        try:
            self._record_attempt(session, GAVE_UP, TOOL, summary, gate=gate)
        except Exception as exc:  # noqa: BLE001 - named below
            notes.append(f"could not record the attempt: {type(exc).__name__}: {exc}")
        if len(notes) > 1:  # fix round 3 K1: an incomplete undo commits nothing tonight
            self.breached = True
        return "; ".join(notes)

    def _drop_log_tail(self, size: int) -> list[str]:
        """F19: the log back to `size` bytes, and the night's records cut with it (07-23: the
        totals never count a dropped line); a refused or failed cut is a note."""
        notes = self._cut_log_tail(size)
        kept = len(self.ledger.expected(ATTEMPT_LOG.as_posix()) or b"")
        self.night_records = [(at, r) for at, r in self.night_records if at < kept]
        return notes

    def _cut_log_tail(self, size: int) -> list[str]:
        rel = ATTEMPT_LOG.as_posix()
        good = (self.ledger.expected(rel) or b"")[:size]
        if not self.ledger.holds(rel):  # fix round 1: put back the driver's prefix
            return [self._breach(rel, good)]
        try:
            if not _truncate(self.log, size):
                return [f"not restored: {rel} (refused: a link or not a file)"]
        except Exception as exc:  # noqa: BLE001 - named in the record
            return [f"not restored: {rel} ({type(exc).__name__}: {exc})"]
        self.ledger.set(rel, good)
        return []

    def _staged(self) -> list[str]:
        """Every path staged in the index (best-effort: an unreadable index is named)."""
        try:
            raw = _git_ok(self._git, ["diff", "--cached", "--name-only", "-z"])
        except Exception as exc:  # noqa: BLE001 - the caller names it
            return [f"<unknown: {type(exc).__name__}: {exc}>"]
        return [n for n in raw.decode("utf-8", "surrogateescape").split("\0") if n]

    # --- naming proposals (07-34; D-19, D-29) ---

    def _after_session(self, session: _Session) -> None:
        """Ruling F34: only a readability session's proposals are applied, so matching nights
        keep the placeholders (D-17) and packs stay complete. Runs after the audit and before
        the session's landing, so its own unit lands under the new names."""
        if session.claim.session == READABILITY:
            self._apply_proposals(session)

    def _apply_proposals(self, session: _Session) -> None:
        """D-19: the driver, the only writer of naming state, reads the session's
        `<attempt dir>/proposals.jsonl` (proposals.read_proposals; a partly bad file line by
        line through parse_line) and applies each proposal in file order under the gate lock.
        The last line for a row (or a header path) wins, as the readability skill says; an
        earlier one is REFUSED as superseded. A line that is not a proposal is a REFUSED record
        with op null naming it, never a night stop. The proposing session's own claim never
        blocks it: its view unit is rewritten in place instead (CONTEXT default). Nothing is
        applied once the night is stopping or after a breach (J2: nothing more is committed)."""
        claim = session.claim
        with self.gate_lock:
            if self.breached or self.stop.is_set():
                return
            for item in _latest_first(_read_proposal_file(claim.proposals)):
                if isinstance(item, str):
                    self._record_rename(None, REFUSED, reason=item)
                elif isinstance(item, _Superseded):
                    self._record_rename(item.proposal, REFUSED, old=self._old_name(item.proposal),
                                        reason=_SUPERSEDED)  # fmt: skip
                else:
                    self._apply_pending(_Pending(item, claim.model, claim), own=_own_key(claim))

    def _apply_pending(self, pending: _Pending, *, own: tuple[str, str] | None,
                       retry: bool = False) -> None:  # fmt: skip
        """One proposal against the naming state of this moment: REFUSED (with its reason),
        DEFERRED behind another live claim (recorded once; `_retry_deferred` tries it again),
        or APPLIED in one gated commit."""
        proposal = pending.proposal
        old = self._old_name(proposal)
        try:
            plan = self._plan_naming(pending, old)
        except _Refusal as refusal:
            self._record_rename(proposal, REFUSED, old=old, reason=refusal.reason)
            return
        blocked = self._blocked(plan.targets, own)
        if blocked:
            self.deferred_renames.append(replace(pending, own=None))
            if not retry:
                self._record_rename(proposal, DEFERRED, old=old, reason=blocked)
            return
        try:
            commit = self._gated_commit(pending, plan, own)
        except _Deferral as deferral:  # a subclass of _Refusal: caught first
            self.deferred_renames.append(replace(pending, own=None))
            if not retry:
                self._record_rename(proposal, DEFERRED, old=old, reason=deferral.reason)
            return
        except _Refusal as refusal:
            self._record_rename(proposal, REFUSED, old=old, reason=refusal.reason)
            return
        except _Stop as stop:  # the gate or the commit failed as a tool: recorded, then stopped
            self._record_rename(proposal, REFUSED, old=old, reason=stop.detail)
            raise
        self._record_rename(proposal, APPLIED, old=old, commit=commit)
        if pending.own is not None and plan.rewrite:
            self._rewrite_view(pending.own, plan.rewrite)

    def _retry_deferred(self, own: tuple[str, str] | None = None) -> None:
        """D-19, CONTEXT default: the proposals DEFERRED behind another live claim are tried
        again, in proposal order, after each claim release (`_claimed`) and once more at the
        end of the night. Nothing is tried once the night is stopping or a breach happened (J2:
        nothing is committed any more). `own` is the unit of the releasing worker's pass, which
        never blocks."""
        if not self.deferred_renames or self.breached or self.stop.is_set():
            return
        with self.gate_lock:
            waiting, self.deferred_renames = self.deferred_renames, []
            for pending in waiting:
                self._apply_pending(pending, own=own, retry=True)

    def _renames_since(self, head: str) -> dict[str, dict[str, str]]:
        """Per EXE, every C name symbols.csv changed between commit `head` (a view's, F34) and
        HEAD, old -> new; a row without a symbols.csv name at `head` had its placeholder. Empty
        when `head` is HEAD (or not given)."""
        now = _git_ok(self._git, ["rev-parse", "--verify", "HEAD^{commit}"]).decode().strip()
        if not head or head == now:
            return {}
        found: dict[str, dict[str, str]] = {}
        for exe in EXE_ORDER:
            before, after = self._c_names_at(head, exe), self._c_names_at(now, exe)
            mapping = {}
            for key in before.keys() | after.keys():
                old = before.get(key, _placeholder(*key))
                new = after.get(key, _placeholder(*key))
                if old != new:
                    mapping[old] = new
            if mapping:
                found[exe] = mapping
        return found

    def _c_names_at(self, commit: str, exe: str) -> dict[tuple[str, int], str]:
        """(kind, address) -> C name of every symbols.csv row of `exe` at `commit` (none: the
        file is not there)."""
        done = self._git(["cat-file", "blob", f"{commit}:{_symbols_rel(exe)}"])
        if done.returncode != 0:
            return {}
        lines = [line for line in done.stdout.decode("utf-8").splitlines()
                 if line and not line.startswith("#")]  # fmt: skip
        return {(row["kind"], int(row["address"], 16)): unitdefs.c_name_of(row["name"], row["kind"])
                for row in csv.DictReader(lines)}  # fmt: skip

    def _old_name(self, proposal: Rename | Header) -> str | None:
        """The C name a rename proposal's row has now (its symbols.csv name's, else its
        placeholder); None for a header, or when symbols.csv cannot be read."""
        if not isinstance(proposal, Rename):
            return None
        try:
            symbols = read_symbols_csv(self.repo / _symbols_rel(proposal.exe))
        except (ValueError, OSError):
            return _placeholder(proposal.kind, proposal.address)
        return _current_c_name(proposal, symbols)

    def _plan_naming(self, pending: _Pending, old: str | None) -> _NamingPlan:
        """What one valid proposal writes and gates; _Refusal (its reason) when it is not
        valid against the naming state of this moment, or when a file it must read cannot be
        read (broken naming state is refused, never guessed)."""
        try:
            if isinstance(pending.proposal, Rename):
                return self._plan_rename(pending, old)
            return self._plan_header(pending.proposal)
        except (ValueError, OSError) as exc:
            raise _Refusal(f"a file the proposal needs could not be read: "
                           f"{type(exc).__name__}: {exc}") from None  # fmt: skip

    def _plan_rename(self, pending: _Pending, old: str | None) -> _NamingPlan:
        """symbols.csv with the row's new linker name and every committed unit that uses the
        old C name as a whole word (the INCLUDE_ASM marker included) with the token rewritten
        (D-19, D-29: `address_of` refuses the old placeholder, so every user changes in the
        same commit)."""
        rename = pending.proposal
        exe = rename.exe
        try:
            symbols = read_symbols_csv(self.repo / _symbols_rel(exe))
            state = self._naming_state(exe, pending.own, symbols)
            problem = rename_problem(rename, **state)
        except (ValueError, OSError) as exc:  # broken naming state: refused, never guessed
            raise _Refusal(f"the naming state of {exe} could not be read: "
                           f"{type(exc).__name__}: {exc}") from None  # fmt: skip
        if problem is not None:
            raise _Refusal(problem)
        rows = _renamed_rows(symbols, rename)
        text = format_symbols_csv(rows, _manifest_name(exe))
        changes: dict[str, bytes | None] = {_symbols_rel(exe): text.encode("utf-8")}
        mapping = {old: rename.name}
        units = self._affected_units(exe, old)
        headers = self._affected_headers(old)
        for rel, data in {**units, **headers}.items():
            changes[rel] = _rewrite(data, mapping)
        gated = {*units, *(self._includers({PurePosixPath(r).name for r in headers})
                           if headers else ())}  # fmt: skip
        subject = f"refactor({exe}): rename {old} to {rename.name}"
        body = [f"{rename.kind} 0x{rename.address:08X} of {exe}: {old} -> {rename.name} "
                f"(linker name {linker_name(rename.name, rename.kind)})"]  # fmt: skip
        return _NamingPlan(changes, _targets(gated), subject, body, {exe: mapping},
                           symbols=(exe, rows))  # fmt: skip

    def _naming_state(self, exe: str, own: _Claim | None, symbols: Sequence[SymbolRow]) -> dict:
        """rename_problem's naming state of `exe` read now: symbols.csv and functions.csv rows,
        the runtime publics of runtime.csv, the file-scope names of the committed units (and
        of the proposing session's view unit) and the EXE's LE data objects (Deps.data_ranges;
        none means every data rename is refused, fail closed)."""
        functions = read_functions_csv(self.repo / "config" / exe / "functions.csv")
        runtime = self.repo / "config" / exe / "runtime.csv"
        publics = ([name for row in read_runtime_csv(runtime) for name in row.publics]
                   if runtime.is_file() else [])  # fmt: skip
        return {"symbols": symbols, "functions": functions, "runtime_names": publics,
                "src_names": self._src_names(exe, own),
                "data_ranges": tuple(self.deps.data_ranges(exe))}  # fmt: skip

    def _src_names(self, exe: str, own: _Claim | None, *, exclude: str | None = None
                   ) -> dict[str, str]:  # fmt: skip
        """File-scope name -> where it is used (unitdefs.file_scope_names): the committed
        src/<exe>/ units, the proposing session's view unit (attempt check's in-session state
        reads the view too), and every committed header under include/: the typedefs of
        common.h (s8..u32) and every name a driver-written header declares (ruling, 07-19 as
        built), so a rename never collides with them."""
        sources = [(rel, self.repo / rel) for rel in self._committed_units(exe)]
        if (own is not None and own.pick.exe == exe and own.view_unit.is_file()
                and not _is_link(own.view_unit)):  # fmt: skip
            sources.append((own.view_unit_rel, own.view_unit))
        sources += [(rel, self.repo / rel) for rel in self._committed_headers()]
        names: dict[str, str] = {}
        for rel, path in sources:
            if rel == exclude:  # fix round 1: a header proposal's own committed text
                continue
            for name in sorted(unitdefs.file_scope_names(path.read_bytes().decode("utf-8"))):
                names.setdefault(name, rel)
        return names

    def _committed_headers(self) -> list[str]:
        """Every header HEAD tracks directly under include/, repo-relative, sorted."""
        raw = _git_ok(self._git, ["ls-files", "-z", "--", "include/"])
        names = raw.decode("utf-8", "surrogateescape").split("\0")
        return sorted(n for n in names if n.endswith(".h") and n.count("/") == 1)

    def _affected_headers(self, old: str) -> dict[str, bytes]:
        """The committed driver-written headers (never common.h or watcom_compat.h, D-19) that
        use `old` as a whole word, with their bytes now: a renamed prototype or extern moves
        with its row."""
        token = _token(old)
        found = {}
        for rel in self._committed_headers():
            if PurePosixPath(rel).name in RESERVED_HEADERS:
                continue
            data = _read(self.repo / rel)
            if data is not None and token.search(data):
                found[rel] = data
        return found

    def _includers(self, names: set[str]) -> list[str]:
        """The committed units of both EXEs that include one of the headers `names`
        (`snd.h`), directly or through other committed headers (unitdefs.included_headers)."""
        includes = {PurePosixPath(rel).name: unitdefs.included_headers(
            (self.repo / rel).read_bytes().decode("utf-8")) for rel in self._committed_headers()}
        closure = set(names)
        grown = True
        while grown:
            grown = False
            for header, included in includes.items():
                if header not in closure and included & closure:
                    closure.add(header)
                    grown = True
        units = [rel for exe in EXE_ORDER for rel in self._committed_units(exe)]
        return [rel for rel in units if unitdefs.included_headers(
            (self.repo / rel).read_bytes().decode("utf-8")) & closure]  # fmt: skip

    def _committed_units(self, exe: str) -> list[str]:
        """Every unit file HEAD tracks under src/<exe>/, repo-relative, sorted."""
        raw = _git_ok(self._git, ["ls-files", "-z", "--", f"src/{exe}/"])
        names = raw.decode("utf-8", "surrogateescape").split("\0")
        return sorted(n for n in names if n.endswith(".c") and n.count("/") == _UNIT_DEPTH)

    def _affected_units(self, exe: str, old: str) -> dict[str, bytes]:
        """The committed units of `exe` that use `old` as a whole word (definition, call,
        extern, INCLUDE_ASM marker, comment), with their bytes now."""
        token = _token(old)
        found = {}
        for rel in self._committed_units(exe):
            data = _read(self.repo / rel)
            if data is not None and token.search(data):
                found[rel] = data
        return found

    def _plan_header(self, header: Header) -> _NamingPlan:
        """D-19's shared-header proposal: the whole text of one include/<name>.h, refused by
        proposals.header_problem (reserved headers, inline asm, pragmas, function-like macros,
        ...); gated with every committed unit that includes it, in the same all-or-nothing
        gate (none: `gate --all`)."""
        problem = header_problem(header) or self._header_names_problem(header)
        if problem is not None:
            raise _Refusal(problem)
        data = header.text.encode("ascii")
        if _read(self.repo / header.path) == data:
            raise _Refusal(f"{header.path} already holds this text")
        includers = self._includers({PurePosixPath(header.path).name})
        body = [f"header {header.path}: {len(data)} bytes, gated with the {len(includers)} "
                f"committed units that include it"]  # fmt: skip
        return _NamingPlan({header.path: data}, _targets(includers),
                           f"refactor(include): write {header.path}", body, {})

    def _header_names_problem(self, header: Header) -> str | None:
        """Fix round 1 (review I2, D-19): every name the header declares or defines
        (unitdefs.declared_names: macros, typedefs, tags, enumerators, prototypes, objects) is
        checked by the rename path's rules: name_problem (keywords, reserved, placeholders such
        as func_/D_/LAB_/PTR_/UNK_), then the C and linker names of both EXEs' symbols.csv rows,
        their runtime publics, and the names every other committed file (units of
        both EXEs, other headers) declares. The names the committed version of the
        header already declares are its own (fix round 2)."""
        names = sorted(unitdefs.declared_names(header.text))
        for name in names:
            problem = name_problem(name)
            if problem is not None:
                return f"{header.path} declares {name}: {problem}"
        current = self.repo / header.path  # equals HEAD (_require_head), or is not there
        own = (unitdefs.declared_names(current.read_bytes().decode("utf-8"))
               if current.is_file() and not _is_link(current) else frozenset())  # fmt: skip
        taken = self._taken_names()
        files = self._declared_elsewhere(header.path)
        for name in names:
            if name in own:  # fix round 2: the committed header already declares it
                continue
            where = taken.get(name) or (f"declared in {files[name]}" if name in files
                                        else None)  # fmt: skip
            if where is not None:
                return f"{header.path} declares {name}, which is already {where}"
        return None

    def _declared_elsewhere(self, exclude: str) -> dict[str, str]:
        """Fix round 2 (re-review I1): name -> the first committed file that DECLARES it
        (unitdefs.declared_names), over the units of both EXEs and every committed header but
        `exclude`. A unit that only uses a header's type or tag (`extern snd_level g;`) does
        not declare it, so the header can still be rewritten."""
        rels = [*(rel for exe in EXE_ORDER for rel in self._committed_units(exe)),
                *self._committed_headers()]  # fmt: skip
        found: dict[str, str] = {}
        for rel in rels:
            if rel == exclude:
                continue
            for name in sorted(unitdefs.declared_names(
                    (self.repo / rel).read_bytes().decode("utf-8"))):  # fmt: skip
                found.setdefault(name, rel)
        return found

    def _taken_names(self) -> dict[str, str]:
        """Every C and linker spelling of both EXEs' symbols.csv rows and runtime publics (a
        runtime public's C name read as a func and as data, fail closed), with where it is
        used."""
        taken: dict[str, str] = {}
        for exe in EXE_ORDER:
            config = self.repo / "config" / exe
            for row in read_symbols_csv(config / "symbols.csv"):
                where = f"used by symbols.csv {exe} {row.kind} 0x{row.address:08X} ({row.name})"
                for spelling in (row.name, unitdefs.c_name_of(row.name, row.kind)):
                    taken.setdefault(spelling, where)
            publics = []
            if (config / "runtime.csv").is_file():
                publics += [n for r in read_runtime_csv(config / "runtime.csv") for n in r.publics]
            if (config / "functions.csv").is_file():
                publics += [r.name for r in read_functions_csv(config / "functions.csv")
                            if r.kind == KIND_RUNTIME]  # fmt: skip
            for public in publics:
                for spelling in (public, public.removesuffix(unitdefs.FUNC_LINK_SUFFIX),
                                 public.removeprefix(unitdefs.DATA_LINK_PREFIX)):  # fmt: skip
                    taken.setdefault(spelling, f"used by the {exe} runtime public {public}")
        return taken

    def _blocked(self, targets: Sequence[str], own: tuple[str, str] | None) -> str | None:
        """Why the proposal waits (D-19, CONTEXT default): an affected unit another live
        session holds (its claim file, or a worker's pass on it). The unit of `own` never
        blocks."""
        busy = self.coordinator.busy if self.coordinator is not None else {}
        with self.cond:
            for target in targets:
                key = _unit_key(target)
                if key == own:
                    continue
                path = self.claims.path(*key)
                if path.exists() or key in busy:
                    shown = path.relative_to(self.repo).as_posix()
                    return (f"the affected unit {target} is held by another live session "
                            f"({shown}); the proposal is tried again when it is released")
        return None

    @contextmanager
    def _rename_claim(self, targets: Sequence[str], own: tuple[str, str] | None,
                      start: int | None) -> Iterator[None]:  # fmt: skip
        """D-06, D-19: one multi-unit claim of kind `rename` over the affected units (all but
        `own`), and each marked busy so the coordinator hands none of them out meanwhile.
        _Deferral when one is taken after all."""
        busy = self.coordinator.busy if self.coordinator is not None else {}
        taken: list[tuple[str, str]] = []
        try:
            with self.cond:
                for target in targets:
                    key = _unit_key(target)
                    if key == own:
                        continue
                    record = {"run": self.config.run_id, "worker": self.worker, "exe": key[0],
                              "unit": key[1], "function": None,
                              "start": None if start is None else f"0x{start:08X}",
                              "kind": KIND_RENAME, "pass": None, "model": None,
                              "claimed_at": datetime.now(UTC).isoformat(timespec="seconds")}
                    if key in busy or not self.claims.take(record):
                        raise _Deferral(f"the affected unit {target} was claimed meanwhile")
                    taken.append(key)
                    busy[key] = _RENAMING
            yield
        finally:
            with self.cond:
                for key in taken:
                    self.claims.release(*key)
                    if busy.get(key) is _RENAMING:
                        del busy[key]
                self.cond.notify_all()

    def _gated_commit(self, pending: _Pending, plan: _NamingPlan,
                      own: tuple[str, str] | None) -> str:  # fmt: skip
        """D-19's all-or-nothing step: every path of the plan must equal HEAD, then each is
        written, one container gate runs over every affected unit, and a pass is one commit
        of explicit paths (the plan's, the gated EXEs' status.csv and the feed). A failure puts
        every path back byte for byte and is a _Refusal naming the gate. Returns the commit."""
        start = pending.proposal.address if isinstance(pending.proposal, Rename) else None
        self._require_head(plan.changes)
        with self._rename_claim(plan.targets, own, start):
            originals = {rel: _read(self.repo / rel) for rel in plan.changes}
            outputs = [*(f"config/{exe}/status.csv" for exe in _gated_exes(plan.targets)), FEED]
            self._guard(*outputs)
            self.pre_gate = {rel: self.ledger.expected(rel) for rel in outputs}
            step = "the proposal's paths could not be written"
            try:
                self._write_plan(plan)
                step = "the rename gate could not run"
                gate = self._naming_gate(plan.targets)
            except Exception as exc:
                self.ledger.note(*outputs)  # what a gate that broke off may have written
                self._put_back(originals)
                notes = self._restore_pre_gate()
                raise _Stop(TOOL, "; ".join([f"{step}: {type(exc).__name__}: {exc}",
                                             *notes])) from exc  # fmt: skip
            self.ledger.note(*outputs)  # the gate's output: the one read-back (_Ledger)
            problem = _naming_gate_problem(gate, plan.targets)
            if problem is not None:
                self._put_back(originals)
                notes = self._restore_pre_gate()
                raise _Refusal("; ".join([problem, *notes]))
            commit = self._commit_naming(pending, plan, [*plan.changes, *outputs], originals)
            self.pre_gate = {}
            return commit

    def _require_head(self, changes: Mapping[str, bytes | None]) -> None:
        """Every path a proposal writes equals HEAD now (D-24 a), so a restore is HEAD's bytes."""
        raw = _git_ok(self._git, ["status", "--porcelain=v1", "--untracked-files=all", "-z",
                                  "--", *changes])  # fmt: skip
        dirty = sorted(parse_status(raw))
        if dirty:
            raise _Refusal(f"paths the proposal writes differ from HEAD: {_listed(dirty)}")

    def _write_plan(self, plan: _NamingPlan) -> None:
        """Every path of the plan written atomically: symbols.csv through write_symbols_csv
        (the bytes the plan computed with format_symbols_csv), the rest as their bytes."""
        symbols_rel = _symbols_rel(plan.symbols[0]) if plan.symbols is not None else None
        for rel, data in plan.changes.items():
            path = self.repo / rel
            if rel == symbols_rel:
                write_symbols_csv(path, plan.symbols[1], _manifest_name(plan.symbols[0]))
            elif data is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                write_atomic(path, data)

    def _naming_gate(self, targets: Sequence[str]) -> GateRun:
        return self.deps.rename_gate(list(targets))

    def _put_back(self, originals: Mapping[str, bytes | None]) -> None:
        """Every path of a failed proposal back to its bytes before (None: removed)."""
        for rel, data in originals.items():
            path = self.repo / rel
            if data is None:
                path.unlink(missing_ok=True)
            else:
                write_atomic(path, data)

    def _commit_naming(self, pending: _Pending, plan: _NamingPlan, paths: Sequence[str],
                       originals: Mapping[str, bytes | None]) -> str:  # fmt: skip
        """The one naming commit (D-19, D-25): explicit literal paths, the proposing model's
        co-author line and `Renamed-By: reverseapoc drive`. A commit that fails is undone and
        stops the night (TOOL); a commit that holds bytes the driver did not write, or a
        foreign commit under it, stops it as a breach (nothing more is committed tonight)."""
        try:  # fix round 1 (review minor 1): nothing written stays behind uncommitted
            message = "\n".join([plan.subject, "", *plan.body, "", coauthor(pending.model),
                                 RENAMED_BY]) + "\n"  # fmt: skip
            old = _git_ok(self._git, ["rev-parse", "--verify", "HEAD^{commit}"]).decode().strip()
        except Exception as exc:
            self._put_back(originals)
            notes = self._restore_pre_gate()
            raise _Stop(TOOL, "; ".join([f"the naming commit could not be prepared: "
                                         f"{type(exc).__name__}: {exc}", *notes])) from exc
        message_file = self.repo.joinpath(DRIVER_DIR, self.config.run_id, RENAME_MSG)
        try:
            self._commit_with_retry(message=message, message_file=message_file, paths=paths)
        except Exception as exc:
            moved = _git_ok(self._git, ["rev-parse", "--verify", "HEAD^{commit}"]).decode().strip()
            if moved != old:
                self.breached = True
                raise _Stop(GUARDRAIL, f"the naming commit failed after HEAD moved: {exc}") from exc
            notes = []
            try:
                _git_ok(self._git, ["restore", "--staged", "--", *paths])
            except Exception as unstage:  # noqa: BLE001 - named in the record
                notes.append(f"could not unstage: {unstage}")
            self._put_back(originals)
            notes += self._restore_pre_gate()
            raise _Stop(TOOL, "; ".join([f"the naming commit failed: {exc}", *notes])) from exc
        new = _git_ok(self._git, ["rev-parse", "--verify", "HEAD^{commit}"]).decode().strip()
        wanted = {**plan.changes, **{rel: self.ledger.expected(rel) for rel in paths
                                     if rel not in plan.changes}}  # fmt: skip
        bad = [rel for rel, data in wanted.items() if not self._committed_as(new, rel, data)]
        foreign = self._foreign_commits(old, new, plan.subject)
        if bad or foreign:
            self.breached = True
            raise _Stop(GUARDRAIL, f"the naming commit {new[:12]} holds bytes the driver did "
                                   f"not write ({_listed(bad)}) or sits on commits it did not "
                                   f"make ({_listed(foreign)}); nothing more is committed")
        return new

    def _rewrite_view(self, claim: _Claim, mappings: Mapping[str, Mapping[str, str]]) -> None:
        """The proposing session's own view unit, rewritten in place, so it lands under the new
        names (CONTEXT default: its own claim never blocks the rename)."""
        mapping = mappings.get(claim.pick.exe)
        unit = claim.view_unit
        if not mapping or _is_link(unit) or not unit.is_file():
            return
        data = unit.read_bytes()
        rewritten = _rewrite(data, mapping)
        if rewritten != data:
            write_atomic(unit, rewritten)

    def _record_rename(self, proposal: Rename | Header | None, outcome: str, *,
                       old: str | None = None, reason: str | None = None,
                       commit: str | None = None) -> None:  # fmt: skip
        """One v2 `rename` record in ruling F12's per-op shape: op rename fills exe, address,
        old and new (C identifiers); op header fills path; a line that is not a proposal (or a
        proposal those fields cannot hold, such as a name that is no C identifier) has op null
        and is REFUSED, its reason naming it. A commit exactly when APPLIED."""
        base = {"kind": KIND_RENAME, "schema": SCHEMA_V2, "run": self.config.run_id,
                "exe": None, "address": None, "old": None, "new": None, "op": None,
                "path": None, "outcome": outcome, "reason": _detail(reason) if reason else None,
                "commit": commit, "date": self.deps.today()}  # fmt: skip
        record = dict(base)
        if isinstance(proposal, Rename):
            record.update(op=OP_RENAME, exe=proposal.exe, address=f"0x{proposal.address:08X}",
                          old=old, new=proposal.name)  # fmt: skip
        elif isinstance(proposal, Header):
            record.update(op=OP_HEADER, path=proposal.path)
        try:
            validate_record(record)
        except RecordError:
            if outcome != REFUSED:
                raise
            record = {**base, "outcome": REFUSED, "commit": None,
                      "reason": _detail(f"{_described(proposal)}: {reason or outcome}")}
        self._append(record)

    # --- records ---

    def _pass(self, pick: Pick) -> int:
        """D-08: this function's pass tonight, one more than its finished passes (read from
        the committed log once per night, then counted up by every capped pass: a tier queue
        offers a capped function again the same night)."""
        return self.passes.get((pick.exe, pick.start), 0) + 1

    def _base(self, claim: _Claim, kind: str) -> dict:
        """The fields every v2 attempt and abort record shares (DEC-07): `function` is the
        pick's C name (ruling F12: aborts too), `start` its address key."""
        return {"kind": kind, "schema": SCHEMA_V2, "run": claim.run, "exe": claim.pick.exe,
                "function": c_name(claim.pick), "unit": claim.pick.unit,
                "start": f"0x{claim.pick.start:08X}", "attempt": claim.n,
                "session": claim.session, "pass": claim.pass_n,
                "worker": self.worker}  # fmt: skip

    def _record_attempt(self, session: _Session, outcome: str, abort: str | None,
                        summary: CheckSummary, *, gate: GateRun | None = None
                        ) -> None:  # fmt: skip
        """A v2 attempt record (DEC-07): v1's fields plus the requested model and budget (the
        session's argv, session.build_argv; 07-30: the pass's, D-09, D-25), the hook blocks,
        the gate's verdict (null when no gate ran) and the sweep evidence (P10). No
        transcript, C text or game bytes (D-23)."""
        use = session.usage
        source, cells = _sweep_evidence(session.claim.attempt_dir)
        record = {**self._base(session.claim, KIND_ATTEMPT), "outcome": outcome,
                  "abort_reason": abort, "turns": use.turns,
                  "tokens": {"input": use.input_tokens, "output": use.output_tokens,
                             "cache_read": use.cache_read_tokens,
                             "cache_creation": use.cache_creation_tokens},
                  "cost_usd": use.cost_usd, "seconds": round(session.seconds, 1),
                  "model": session.text("model"),
                  "cli_version": session.text("claude_code_version"),
                  "check": summary.to_json(), "pack_bytes": session.pack.pack_bytes,
                  "truncated": list(session.pack.truncated), "date": self.deps.today(),
                  "model_requested": session.claim.model,
                  "budget_usd": session.claim.budget_usd,
                  "hook_blocks": _hook_blocks(session.events),
                  "gate": _gate_field(gate, session.claim.pick),
                  "sweep_source": source, "sweep_cells_100": cells}  # fmt: skip
        self._append(record)

    def _record_abort(self, claim: _Claim, retries: int) -> None:
        record = {**self._base(claim, KIND_ABORT), "abort_reason": TRANSIENT, "retries": retries,
                  "date": self.deps.today()}  # fmt: skip
        self._append(record)

    def _record_limit(self, seconds: int, streak: int) -> None:
        """DEC-06: one usage-limit wait of this worker (D-07: it pauses every worker)."""
        record = {"kind": KIND_LIMIT, "schema": SCHEMA_V2, "run": self.config.run_id,
                  "worker": self.worker, "seconds": seconds, "streak": streak,
                  "date": self.deps.today()}  # fmt: skip
        self._append(record)

    def _record_run(self, event: str, reason: str, detail: str | None = None, *,
                    checks_failed: Sequence[str] = (), uncommitted: Sequence[str] = (),
                    guard: bool = True, recovered: Sequence[Mapping] = ()) -> None:  # fmt: skip
        """A v2 run record (DEC-06): the night's workers, the stale claims recovered at STARTED
        and, on ENDED and STOPPED, the totals over the night's own records."""
        with self.gate_lock:  # the totals and the append see the same records
            totals = None if event == STARTED else self._night_totals()
            record = {"kind": KIND_RUN, "schema": SCHEMA_V2, "run": self.config.run_id,
                      "event": event, "reason": reason, "detail": detail,
                      "sessions": self.sessions, "matched": self.matched,
                      "checks_failed": list(checks_failed), "uncommitted": list(uncommitted),
                      "date": self.deps.today(), "workers": self.config.workers,
                      "recovered": [{key: c[key] for key in ("exe", "unit", "run")}
                                    for c in recovered],
                      "totals": totals}  # fmt: skip
            self._append(record, guard=guard)

    def _night_totals(self) -> dict:
        """`_totals` over this night's attempt, abort and limit records."""
        mine = [r for _, r in self.night_records if r.get("run") == self.config.run_id]
        limits = [r for r in mine if r["kind"] == KIND_LIMIT]
        sessions = [r for r in mine if r["kind"] in (KIND_ATTEMPT, KIND_ABORT)]
        return _totals(sessions, max(0.0, self.deps.clock() - self.night_start), limits)

    def _append(self, record: Mapping, *, guard: bool = True) -> None:
        """Every driver record goes through here (fix round 1): the log must still hold the
        driver's bytes, then the ledger records those bytes plus the line, never a read-back.
        After a breach (nothing is committed any more) the check is skipped, so the STOPPED
        record can always be written. 07-18 (D-27 P4): every append holds the gate lock, so a
        record of another worker waits while a landing runs, and F19's truncation of a failed
        match commit can only drop that landing's own MATCHED line."""
        rel = ATTEMPT_LOG.as_posix()
        with self.gate_lock:
            line = record_line(record)
            checked = guard and not self.breached
            if checked:
                self._guard(rel)
            before = self.ledger.expected(rel) if checked else _read(self.log)
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with self.log.open("ab") as fh:
                fh.write(line)
            self.ledger.set(rel, (before or b"") + line)
            self.night_records.append((len(before or b""), dict(record)))


# ---- naming proposals (07-34; D-19) ----

RENAMED_BY = "Renamed-By: reverseapoc drive"  # the trailer of every naming commit (D-19)
RENAME_MSG = "rename-msg.txt"  # under build/driver/<run>/: the last naming commit's message
_UNIT_DEPTH = 2  # src/<exe>/<unit>.c: two slashes
_SUPERSEDED = "superseded by a later line for the same row (the last line for a row wins)"
_RENAMING = object()  # a coordinator `busy` mark: a unit a naming commit holds (D-06)


class _Refusal(Exception):
    """A proposal the driver will not apply now; `reason` goes into its REFUSED record."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _Deferral(_Refusal):
    """A proposal that waits for another live claim's release (DEFERRED)."""


@dataclass(frozen=True)
class _Pending:
    """One proposal to apply: the model of the session that wrote it (its co-author line) and
    that session's claim while it is live (its own unit never blocks; its view is rewritten)."""

    proposal: Rename | Header
    model: str
    own: _Claim | None


@dataclass(frozen=True)
class _Superseded:
    """A proposal a later line of the same file replaced (the same row, or the same header)."""

    proposal: Rename | Header


@dataclass(frozen=True)
class _NamingPlan:
    """What one valid proposal does: the bytes of every path it writes (None: removed), the
    affected units the gate checks (`exe/unit`), the commit's subject and body, the symbols.csv
    rows it writes (`symbols`: (exe, rows), written with write_symbols_csv), and per EXE the
    C names it changes (old -> new), which the proposing session's view takes too."""

    changes: dict[str, bytes | None]
    targets: tuple[str, ...]
    subject: str
    body: list[str]
    rewrite: dict[str, dict[str, str]]
    symbols: tuple[str, tuple[SymbolRow, ...]] | None = None


def _read_proposal_file(path: Path) -> list[Rename | Header | str]:
    """The proposals of one proposals.jsonl in file order: the bytes proposals.read_proposals(
    path) reads (read_bounded: one handle, at most PROPOSALS_FILE_MAX + 1 bytes; fix round 2),
    parsed with parse_proposals. A file with a bad line is parsed again line by line from the
    same bytes (parse_line), each bad line a string naming it, so the good lines still apply; a
    file that cannot be read at all (a link or not a regular file, too large, not UTF-8,
    unreadable) is one string."""
    if os.path.lexists(path) and (_is_link(path) or not path.is_file()):  # fix round 1, S7
        return [f"{path.name}: not a regular file (a link, a junction or a directory); refused "
                "whole, never followed"]
    try:
        data = read_bounded(path)
    except ProposalError as exc:  # refused whole (its size): no line is read
        return [str(exc)]
    except OSError as exc:
        return [f"{path.name}: {type(exc).__name__}: {exc}"]
    if data is None:
        return []
    try:
        return list(parse_proposals(data))
    except ProposalError as exc:
        first = str(exc)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{path.name} {first}"]
    found: list[Rename | Header | str] = []
    for lineno, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            continue
        try:
            found.append(parse_line(line, lineno))
        except ProposalError as exc:
            found.append(f"{path.name} {exc}")
    return found


def _proposal_key(proposal: Rename | Header) -> tuple:
    if isinstance(proposal, Rename):
        return proposal.exe, proposal.kind, proposal.address
    return (proposal.path,)


def _latest_first(
    items: Sequence[Rename | Header | str],
) -> list[Rename | Header | str | _Superseded]:
    """`items` in file order, each proposal a later one for the same row or header replaces
    marked _Superseded (the readability skill: the last line for a row wins)."""
    last = {_proposal_key(item): i for i, item in enumerate(items) if not isinstance(item, str)}
    return [item if isinstance(item, str) or last[_proposal_key(item)] == i else _Superseded(item)
            for i, item in enumerate(items)]  # fmt: skip


def _own_key(claim: _Claim) -> tuple[str, str]:
    return claim.pick.exe, claim.pick.unit


def _unit_key(target: str) -> tuple[str, str]:
    exe, _, unit = target.partition("/")
    return exe, unit


def _target_of(rel: str) -> str:
    """`src/<exe>/<unit>.c` -> `<exe>/<unit>`, the gate's target spelling."""
    path = PurePosixPath(rel)
    return f"{path.parent.name}/{path.stem}"


def _targets(units: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({_target_of(rel) for rel in units}))


def _gated_exes(targets: Iterable[str]) -> list[str]:
    exes = {_unit_key(target)[0] for target in targets}
    return [exe for exe in EXE_ORDER if exe in exes]


def _symbols_rel(exe: str) -> str:
    return f"config/{exe}/symbols.csv"


def _manifest_name(exe: str) -> str:
    return f"{exe.upper()}.EXE"


def _placeholder(kind: str, address: int) -> str:
    return game_name(address) if kind == unitdefs.FUNC_KIND else data_name(address)


def _current_c_name(rename: Rename, symbols: Sequence[SymbolRow]) -> str:
    """The C name the row has now: its symbols.csv name's (unitdefs.c_name_of), else its
    placeholder."""
    for row in symbols:
        if row.address == rename.address and row.kind == rename.kind:
            return unitdefs.c_name_of(row.name, row.kind)
    return _placeholder(rename.kind, rename.address)


def _renamed_rows(symbols: Sequence[SymbolRow], rename: Rename) -> tuple[SymbolRow, ...]:
    """symbols.csv's rows with the renamed row's new linker name (added when it had none),
    sorted by address."""
    new = SymbolRow(rename.address, linker_name(rename.name, rename.kind), rename.kind)
    kept = [row for row in symbols if row.address != rename.address]
    return tuple(sorted([*kept, new], key=lambda row: row.address))


def _token(name: str) -> re.Pattern[bytes]:
    """`name` as a whole word, the exact token (`\\b` on both sides: `_` and digits are word
    characters, so func_00010010 never matches inside func_000100100)."""
    return re.compile(rb"\b" + re.escape(name.encode("ascii")) + rb"\b")


def _rewrite(data: bytes, mapping: Mapping[str, str]) -> bytes:
    """Every whole-word use of each old name in `data` replaced by its new name, all at once
    (a chain or a swap of names never cascades), byte for byte elsewhere."""
    if not mapping:
        return data
    names = sorted(mapping, key=len, reverse=True)
    pattern = re.compile(rb"\b(" + rb"|".join(re.escape(n.encode("ascii")) for n in names)
                         + rb")\b")  # fmt: skip
    return pattern.sub(lambda m: mapping[m.group(1).decode("ascii")].encode("ascii"), data)


def _naming_gate_problem(gate: GateRun, targets: Sequence[str]) -> str | None:
    """Why a naming gate run is no pass: any exit but 0, or a pass whose SHA-1s do not name
    both EXEs (the landing's minor 7 rule)."""
    shown = " ".join(targets) or "--all"
    if gate.exit_code != EXIT_OK:
        return f"gate {shown} exited {gate.exit_code}"
    stems = sorted(PurePosixPath(name).stem.lower() for name, _ in gate_sha1s(gate.doc))
    if stems != sorted(EXE_ORDER):
        return f"gate {shown} passed but its SHA-1s name {stems}, not both of {sorted(EXE_ORDER)}"
    return None


def _described(proposal: Rename | Header | None) -> str:
    """A proposal named for a record whose op is null (its fields cannot hold it)."""
    if isinstance(proposal, Rename):
        return (f"rename of {proposal.exe} {proposal.kind} 0x{proposal.address:08X} to "
                f"{proposal.name!r}")  # fmt: skip
    if isinstance(proposal, Header):
        return f"header {proposal.path!r}"
    return "proposal"


def rename_gate_argv(targets: Sequence[str]) -> list[str]:
    """D-19: one container gate over every affected unit, all or nothing; with none (nothing
    in src/ names the row) `gate --all`, which re-checks every matched unit and writes nothing."""
    return [*CONTAINER_CLI, "gate", *(targets or ("--all",)), "--json"]


def _rounded(value: float) -> float:
    return round(value, 6)


def _share(records: Sequence[Mapping]) -> dict:
    """One `by_model` or `by_session` entry: sessions, matches, cost."""
    return {"sessions": len(records), "matched": sum(r["outcome"] == MATCHED for r in records),
            "cost_usd": _rounded(sum(r["cost_usd"] for r in records))}  # fmt: skip


def _group(records: Sequence[Mapping], key: str) -> dict:
    keys = dict.fromkeys(r[key] for r in records)
    return {name: _share([r for r in records if r[key] == name]) for name in keys}


def _totals(records: Sequence[Mapping], wall_seconds: float, limits: Sequence[Mapping]) -> dict:
    """DEC-06's nightly totals (research section 8), computed from the night's own records so
    they add up by construction (T-07-68): `records` are its attempt and abort records, `limits`
    its limit records, `wall_seconds` the night's wall clock. Counted sessions by outcome,
    turns, the four token classes, cost and session seconds are sums over the attempt
    records; hook blocks and the regressions the gate stopped too; then the limit waits, the
    aborts, and sessions, matches and cost per requested model and per session kind."""
    attempts = [r for r in records if r["kind"] == KIND_ATTEMPT]
    gates = [r["gate"] for r in attempts if r["gate"] is not None]
    return {
        "sessions": {o: sum(r["outcome"] == o for r in attempts) for o in _V2_OUTCOMES},
        "turns": sum(r["turns"] for r in attempts),
        "tokens": {k: sum(r["tokens"][k] for r in attempts) for k in _COUNT_KEYS},
        "cost_usd": _rounded(sum(r["cost_usd"] for r in attempts)),
        "session_seconds": _rounded(sum(r["seconds"] for r in attempts)),
        "wall_seconds": _rounded(wall_seconds),
        "hook_blocks": sum(r["hook_blocks"] for r in attempts),
        "regressions_stopped": sum(g["regressions"] for g in gates),
        "limit_waits": {"count": len(limits),
                        "seconds": _rounded(sum(r["seconds"] for r in limits))},
        "aborts": sum(r["kind"] == KIND_ABORT for r in records),
        "by_model": _group(attempts, "model_requested"),
        "by_session": _group(attempts, "session"),
    }  # fmt: skip


def drive(config: DriveConfig, deps: Deps, *, lock: ProcessLock | None = None) -> DriveReport:
    """Run one night (see the module docstring), under the verb's held drive.lock `lock`, or
    under its own when none is given."""
    return _Night(config, deps).run(lock)

# ---- the drive verb (plan 06-25; D-10, D-13, D-24, D-34, D-36, D-48) ----

COMPOSE_RUN = ("docker", "compose", "run", "--rm", "-T", "build")  # -T: output is captured
CONTAINER_CLI = (*COMPOSE_RUN, "uv", "run", "--frozen", "reverseapoc")  # D-24: the gates
COMMAND_TIMEOUT_S = 3600  # a gate re-checks a unit and rebuilds both EXEs; generous, never forever
DRY_RUN_DIR = "dry-run"  # build/driver/<run>/dry-run/<exe>/<func>/context.md
DRY_RUN_TIER_PICKS = PILOT_PER_EXE * len(EXE_ORDER)  # 07-26: the tier dry run shows as many


@dataclass(frozen=True)
class DriveOptions:
    """What `reverseapoc drive` was asked to do (D-07 defaults: 3 workers, a night cap of 60
    launched sessions, no match target; 07-30: the per-model session budgets, the turns and
    the per-session wall clock, and the canary's model)."""

    repo: Path
    run_id: str
    max_sessions: int = 60
    target_matched: int = 0  # 0: off
    workers: int = 3
    dry_run: bool = False
    canary: bool = False
    json: bool = False
    max_budget_usd: float = MAX_BUDGET_USD  # D-07: per Opus session
    fable_budget_usd: float = FABLE_BUDGET_USD  # D-25: per Fable session
    max_turns: int = MAX_TURNS  # D-07
    session_minutes: int = TIMEOUT_S // 60  # D-07: each session's wall clock
    canary_model: str = MODEL  # D-25: the owner's canary may ask for Fable
    session: str = MATCHING  # 07-38 (D-18): `drive --session matching|readability`

    @property
    def config_root(self) -> Path:
        return Path(self.repo) / "config"

    @property
    def run_dir(self) -> Path:
        return Path(self.repo).joinpath(DRIVER_DIR, self.run_id)


@dataclass(frozen=True)
class ExeWorld:
    """One EXE as the picker and a session need it: score's P16 survivors (`pool`, D-09), the
    unit of every row start, the callees of every row start (picker.requeue), and the two
    builders that touch files: the D-13 context pack into a directory under build/driver/ and
    the D-12 unit scaffold. For the tier queue (07-26): `ranks`, every game/thunk row as score
    ranks it with no P16 filter, and `graph`, the EXE's call graph (callgraph.build_for, built
    on first call; None: the world has none, so it cannot serve a signed tier)."""

    pool: Sequence[Candidate]
    units: Mapping[int, str]
    callees: Mapping[int, tuple[int, ...]]
    pack: Callable[..., PackInfo]  # (pick, directory[, src root]); the src default: src/
    scaffold: Callable[[Pick, Path], None]  # (pick, the file to write)
    ranks: Mapping[int, Candidate] = field(default_factory=dict)
    graph: Callable[[], CallGraph] | None = None
    # 07-34 (D-19): the EXE's LE data objects, where a data rename must lie (SymbolTable's rule)
    data_ranges: tuple[tuple[int, int], ...] = ()


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]


@dataclass(frozen=True)
class Seams:
    """Every effect of the verb: `run` runs every command except git and the session (docker,
    uv, `claude --version`) and returns its exit code and text output; `git` is git_runner;
    `world` loads both EXEs; `session` is session.run_session and `argv` the claude argv
    (session.build_argv with the resolved `claude`; Deps.argv's keyword signature, 07-30).
    `now` is the wall clock the console stamps read (local time; Deps.clock stays the
    monotonic clock for durations)."""

    run: Runner
    git: Callable[..., subprocess.CompletedProcess]  # Deps.git: (args) or (args, input=bytes)
    world: Callable[[], Mapping[str, ExeWorld]]
    session: Callable[..., SessionResult]
    argv: Callable[..., Sequence[str]]  # (prompt, *, model, max_budget_usd, max_turns)
    claude: str = "claude"
    base_env: Mapping[str, str] | None = None
    now: Callable[[], datetime] = datetime.now


def stamp(now: datetime) -> str:
    """The `[HH:MM:SS] ` prefix of a console line: the time it printed."""
    return now.strftime(STAMP_FORMAT)


def console(options: DriveOptions, seams: Seams) -> Callable[[str], None]:
    """F13: in --json mode stdout keeps one JSON document and the console prints nothing; in
    text mode each progress line goes to stderr stamped with the local time it prints (quick
    261026-9ue). The clock and sys.stderr are read on every call, never once per run."""
    if options.json:
        return _quiet

    def say(text: str) -> None:
        print(stamp(seams.now()) + CONSOLE_PREFIX + text, file=sys.stderr, flush=True)

    return say


def command_runner(repo: Path, *, timeout_s: float = COMMAND_TIMEOUT_S) -> Runner:
    """argv in `repo` (compose.yaml is at its root), never a shell, text output captured. A
    missing program is exit 127 and a timeout exit 124, so no command can raise its way past a
    refusal or a gate."""

    def run(argv: Sequence[str]) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(list(argv), cwd=repo, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout_s,
                                  stdin=subprocess.DEVNULL, check=False)  # fmt: skip
        except OSError as exc:  # fix round 1 I2: not only a missing program
            return subprocess.CompletedProcess(list(argv), _os_error_exit(exc), "",
                                               f"{argv[0]}: {exc}")
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(list(argv), 124, "",
                                               f"ran longer than {timeout_s:g} s")  # fmt: skip

    return run


def _target(pick: Pick) -> str:
    return f"{pick.exe}/{pick.unit}"


def gate_argv(pick: Pick, attempts: int) -> list[str]:
    """D-24: the container gate of the claimed unit, recording `attempts`."""
    return [*CONTAINER_CLI, "gate", _target(pick), "--attempts", str(attempts), "--json"]


def partial_gate_argv(pick: Pick, src: str, attempts: int) -> list[str]:
    """F7: `gate --partial` on the saved best C, a repo-relative POSIX path (/work in the
    container)."""
    return [*CONTAINER_CLI, "gate", _target(pick), "--partial", "--src", src,
            "--attempts", str(attempts), "--json"]  # fmt: skip


def lint_argv(pick: Pick) -> list[str]:
    """The C89 lint of the claimed unit, in the container where clang is (06-15 notes)."""
    return [*CONTAINER_CLI, "lint", f"src/{pick.exe}/{pick.unit}.c", "--json"]


def _json_doc(text: str) -> Mapping | None:
    try:
        doc = json.loads(text)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def _status_rows(config_root: Path, exe: str) -> list:
    return read_status(status_path(config_root, exe))


def excluded_keys(config_root: Path, today: str) -> frozenset[Key]:
    """D-09: the starts the picker skips besides the difficult list: every matched row, and
    every partial row of this pass (dated `today`; a partial row from an earlier day is
    eligible again)."""
    out: set[Key] = set()
    for exe in EXE_ORDER:
        for row in _status_rows(config_root, exe):
            if row.status == STATUS_MATCHED or (row.status == STATUS_PARTIAL and row.date == today):
                out.add((exe, row.start))
    return frozenset(out)


def matched_keys(config_root: Path) -> frozenset[Key]:
    return frozenset((exe, row.start) for exe in EXE_ORDER
                     for row in _status_rows(config_root, exe)
                     if row.status == STATUS_MATCHED)  # fmt: skip


def _pools(worlds: Mapping[str, ExeWorld]) -> dict[str, Sequence[Candidate]]:
    return {exe: worlds[exe].pool for exe in EXE_ORDER}


def _units(worlds: Mapping[str, ExeWorld]) -> dict[str, Mapping[int, str]]:
    return {exe: worlds[exe].units for exe in EXE_ORDER}


def _callee_keys(worlds: Mapping[str, ExeWorld], key: Key) -> tuple[Key, ...]:
    exe, start = key
    return tuple((exe, callee) for callee in worlds[exe].callees.get(start, ()))


def _container_gate(run: Runner, argv: Sequence[str]) -> GateRun:
    done = run(argv)
    return GateRun(done.returncode, _json_doc(done.stdout or ""))


END_OF_RUN = (
    ("ninja verify", "end-ninja-verify.log",
     (*COMPOSE_RUN, "bash", "-lc",
      "uv run --frozen python configure.py && ninja -t clean && ninja verify")),
    ("gate --all", "end-gate-all.log", (*CONTAINER_CLI, "gate", "--all", "--json")),
)  # fmt: skip


def finish(run: Runner, *, run_dir: Path, say: Callable[[str], None] = _quiet) -> list[str]:
    """D-24: the end-of-run checks, in the container and in this order: a from-clean ninja
    verify (configure, clean, verify), then `gate --all`. Both always run; each one's output is
    written by the driver to build/driver/<run>/end-*.log. Returns one string per failed check
    (`ninja verify exit 1`), which the driver pins in the ENDED record before the chore commit
    (06-23 fix round 4 L1: wired as Deps.end_of_run). Each check's start is named through `say`
    (the verb wires the stamped console; silent by default, quick 261026-9ue)."""
    failed = []
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, log, argv in END_OF_RUN:
        say(f"end of run: {name}: started")
        done = run(list(argv))
        text = (f"$ {' '.join(argv)}\nexit {done.returncode}\n--- stdout\n{done.stdout or ''}"
                f"\n--- stderr\n{done.stderr or ''}\n")  # fmt: skip
        (run_dir / log).write_text(text, encoding="utf-8", newline="\n")
        if done.returncode != 0:
            failed.append(f"{name} exit {done.returncode}")
    return failed


def compose_project(repo: Path) -> str:
    """The compose project name of the checkout: its directory name, lower case, with every
    character but [a-z0-9_-] dropped (compose's own normalization)."""
    return re.sub(r"[^a-z0-9_-]", "", Path(repo).name.lower())


def container_remover(repo: Path, run: Runner) -> Callable[[str], None]:
    """Pitfall 7: after a session, remove every container of the checkout's compose project
    whose name starts with the attempt's prefix (attempt.container_prefix), such as a check
    container left running after a timeout. A failing docker call is a DriverError; the driver
    records it and stops the night after the audit (06-23 S1)."""
    project = compose_project(repo)

    def remove(prefix: str) -> None:
        done = run(["docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={project}",
                    "--filter", f"name={prefix}", "--format", "{{.Names}}"])  # fmt: skip
        if done.returncode != 0:
            raise DriverError(f"docker ps failed: exit {done.returncode} "
                              f"{(done.stderr or '').strip()}")  # fmt: skip
        names = [name for name in (done.stdout or "").split() if name.startswith(prefix)]
        if not names:
            return
        gone = run(["docker", "rm", "-f", *names])
        if gone.returncode != 0:
            raise DriverError(f"docker rm -f {' '.join(names)} failed: exit {gone.returncode}")

    return remove


TierSource = Callable[[Mapping[Key, int] | None], TierQueue]


def tier_source(config_root: Path, worlds: Mapping[str, ExeWorld]) -> TierSource | None:
    """07-26 (DEC-02): when config/mechanics.toml has a signed tier whose digest still matches
    (mechanics.signed_tiers), a builder of a fresh tier queue (picker.tier_queue) over the
    committed members file, the worlds' call graphs, ranks and units, with the matched set of
    status.csv read when it is called; the argument is the finished passes per function
    (pass_index; a night binds its own). None without such a tier: the Phase 6 pools stay."""
    root = Path(config_root)
    if not (root / mechanics.MECHANICS_TOML).is_file():
        return None
    mech, rows = mechanics.read_committed(root)
    if not mechanics.signed_tiers(mech, rows):
        return None
    exes = {row.exe for row in rows}
    graphs = {exe: world.graph() for exe, world in worlds.items()
              if exe in exes and world.graph is not None}  # fmt: skip
    ranks = {exe: world.ranks for exe, world in worlds.items()}

    def build(passes: Mapping[Key, int] | None = None) -> TierQueue:
        return tier_queue(mech, rows, graphs, ranks, _units(worlds),
                          matched=matched_keys(root), passes=passes)  # fmt: skip

    return build


def real_deps(options: DriveOptions, seams: Seams, worlds: Mapping[str, ExeWorld], *,
              today: str | None = None) -> Deps:  # fmt: skip
    """The Deps a real night uses: the picker over both pools minus status.csv's matched and
    this pass's partial rows (AGT-07), picker.requeue with the matched set read now, the
    worlds' scaffold and pack, the claude argv and session, and the container lint and gates
    (D-24). `today` (UTC) names this pass. With a signed tier (07-26) `queue` is the tier
    queue instead (`tier_source`): it never reads the difficult list, whose passes it takes
    from the night's pass index (the committed log), and `requeue` gives nothing back."""
    day = today or _today()
    config_root = options.config_root
    excluded = excluded_keys(config_root, day)
    say = console(options, seams)
    tiers = tier_source(config_root, worlds)

    def pools(difficult: Container[Key]) -> Iterable[Pick]:
        return picker_queue(_pools(worlds), units=_units(worlds), excluded=excluded,
                            difficult=difficult)  # fmt: skip

    def queue(difficult: Container[Key]) -> Iterable[Pick] | TierQueue:
        return pools(difficult) if tiers is None else tiers(None)

    def requeue(difficult: Mapping[Key, tuple[Key, ...]]) -> Iterable[Key]:
        if tiers is not None:
            return ()
        keys = frozenset(difficult)
        empty = next(iter(pools(keys)), None) is None
        callees = {key: _callee_keys(worlds, key) for key in difficult}
        return picker_requeue(difficult, matched=matched_keys(config_root), callees=callees,
                              pool_empty=empty)  # fmt: skip

    def matched_callees(pick: Pick) -> tuple[Key, ...]:
        matched = matched_keys(config_root)
        return tuple(k for k in _callee_keys(worlds, (pick.exe, pick.start)) if k in matched)

    def lint(pick: Pick) -> int:
        code = seams.run(lint_argv(pick)).returncode
        return code if code in (EXIT_OK, EXIT_MISMATCH) else EXIT_TOOL

    return Deps(queue=queue, requeue=requeue, matched_callees=matched_callees,
                scaffold=lambda pick, dest: worlds[pick.exe].scaffold(pick, dest),
                pack=lambda pick, directory, src: worlds[pick.exe].pack(pick, directory, src),
                argv=seams.argv, session=seams.session, lint=lint,
                gate=lambda pick, n: _container_gate(seams.run, gate_argv(pick, n)),
                partial_gate=lambda pick, src, n: seams.run(
                    partial_gate_argv(pick, src, n)).returncode,
                remove_containers=container_remover(options.repo, seams.run),
                rename_gate=lambda targets: _container_gate(seams.run, rename_gate_argv(targets)),
                data_ranges=lambda exe: worlds[exe].data_ranges,
                git=seams.git, today=lambda: day, say=say,
                end_of_run=lambda: finish(seams.run, run_dir=options.run_dir, say=say))  # fmt: skip


def _emit(options: DriveOptions, doc: Mapping, text: Sequence[str]) -> None:
    """F13: in --json mode stdout carries exactly this one JSON document; else the text."""
    if options.json:
        print(json.dumps(doc, separators=(",", ":")))
    else:
        for line in text:
            print(line)


DryPick = Pick | TierItem  # a dry-run pick: a Phase 6 pick, or a tier pick with its place


def _pick_of(entry: DryPick) -> Pick:
    return entry.pick if isinstance(entry, TierItem) else entry


def _pick_doc(options: DriveOptions, entry: DryPick, pack: Path, info: PackInfo) -> dict:
    """One dry-run pick; a tier pick (07-26, ruling F8) adds its tier, level and pass."""
    pick = _pick_of(entry)
    doc = {"exe": pick.exe, "start": f"0x{pick.start:08X}", "name": pick.name,
           "unit": pick.unit, "size": pick.size, "score": pick.score,
           "pack": pack.relative_to(options.repo).as_posix(),
           "pack_bytes": info.pack_bytes}  # fmt: skip
    if isinstance(entry, TierItem):
        doc.update({"tier": entry.tier, "level": entry.level, "pass": entry.pass_n})
    return doc


def tier_picks(options: DriveOptions, worlds: Mapping[str, ExeWorld],
               count: int) -> list[TierItem] | None:  # fmt: skip
    """07-26 (ruling F8): the tier queue's first `count` distinct picks (TierQueue.preview), each
    at its next pass by the committed log's pass index; None without a signed tier."""
    source = tier_source(options.config_root, worlds)
    if source is None:
        return None
    return source(pass_index(Path(options.repo) / ATTEMPT_LOG)).preview(count)


def pilot_picks(options: DriveOptions, worlds: Mapping[str, ExeWorld], *,
                today: str) -> list[DryPick]:  # fmt: skip
    """D-10: the pilot's 10 picks (5 + 5, interleaved, variety rule), skipping status.csv's
    matched and this pass's partial rows and the difficult list. With a signed tier (07-26,
    ruling F8): the tier queue's first 10 picks instead, with their tier, level and pass."""
    tiers = tier_picks(options, worlds, DRY_RUN_TIER_PICKS)
    if tiers is not None:
        return list(tiers)
    difficult = load_difficult(Path(options.repo) / DIFFICULT)
    return picker_pilot(_pools(worlds), units=_units(worlds),
                        excluded=excluded_keys(options.config_root, today),
                        difficult=frozenset(difficult))  # fmt: skip


def night_top_picks(options: DriveOptions, worlds: Mapping[str, ExeWorld], *,
                    today: str) -> list[Pick]:  # fmt: skip
    """The queue's first `max_sessions` picks: no night attempts more functions than that, so
    their Ghidra drafts are the ones worth precomputing (D-13). With a signed tier (07-26,
    ruling F8): the tier queue's first `max_sessions` distinct picks."""
    tiers = tier_picks(options, worlds, options.max_sessions)
    if tiers is not None:
        return [item.pick for item in tiers]
    difficult = frozenset(load_difficult(Path(options.repo) / DIFFICULT))
    stream = picker_queue(_pools(worlds), units=_units(worlds),
                          excluded=excluded_keys(options.config_root, today),
                          difficult=difficult)  # fmt: skip
    return [pick for _, pick in zip(range(options.max_sessions), stream, strict=False)]


def dry_run(options: DriveOptions, worlds: Mapping[str, ExeWorld],
            picks: Sequence[DryPick]) -> int:  # fmt: skip
    """The pilot picks with their packs built under build/driver/<run>/dry-run/; no claude, no
    gate (D-10). A tier pick's line and document add its tier, level and pass (07-26)."""
    docs, lines = [], []
    for entry in picks:
        pick = _pick_of(entry)
        directory = options.run_dir / DRY_RUN_DIR / pick.exe / f"func_{pick.start:08X}"
        info = worlds[pick.exe].pack(pick, directory)
        doc = _pick_doc(options, entry, directory / PACK_FILE, info)
        docs.append(doc)
        place = "" if "tier" not in doc else (
            f" tier {doc['tier']} level {doc['level']} pass {doc['pass']}")
        lines.append(f"{pick.exe} {doc['start']} {pick.name} {pick.unit} size {pick.size} "
                     f"score {pick.score} pack {doc['pack']} ({info.pack_bytes} bytes){place}")
    _emit(options, {"picks": docs}, lines)
    return EXIT_OK


# ---- the preflight (D-13, D-34, D-36; F13, F14) ----

PREFLIGHT_LOG = "preflight.log"
STAMP_FORMAT = "[%H:%M:%S] "  # local wall-clock time on each console line (quick 261026-9ue)
CONSOLE_PREFIX = "drive: "
HOST_CLI = ("uv", "run", "--frozen", "reverseapoc")
DOCKER_INFO = ("docker", "info")
CONTAINER_SYNC = (*COMPOSE_RUN, "uv", "sync", "--locked")
HOST_SYNC = ("uv", "sync", "--locked")
# 06-23 security notes: the hooks run `python -I` (PYTHONDONTWRITEBYTECODE ignored) and import
# reverseapoc lazily down to configure.py; compiled first, no session writes a .pyc.
COMPILE = ("uv", "run", "--frozen", "python", "-m", "compileall", "-q", "tools", "configure.py")
DRAFTS_SOME_MISSING = 1  # ghidra-export --drafts: ran, but some drafts could not be made


class Refused(Exception):
    """The verb refuses to start (exit 2): `reason` is the short name, `detail` the text."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = _detail(detail)


def take_drive_lock(repo: Path) -> ProcessLock:
    """D-06: build/driver/drive.lock of `repo`, now held by the caller (who releases it).
    Refused ("drive lock") when another holder has it or it cannot be opened."""
    lock = ProcessLock(Path(repo) / DRIVE_LOCK)
    shown = DRIVE_LOCK.as_posix()
    try:
        got = lock.try_acquire()
    except OSError as exc:
        raise Refused("drive lock", f"refusing to start: cannot lock {shown}: "
                                    f"{type(exc).__name__}: {exc}") from exc  # fmt: skip
    if not got:
        raise Refused("drive lock", f"refusing to start: another reverseapoc drive is running "
                                    f"({shown} is held)")  # fmt: skip
    return lock


class _Log:
    """F13: every preflight command's argv, exit, stdout and stderr appended to
    build/driver/<run>/preflight.log, so stdout keeps one JSON document in --json mode. In text
    mode each command is also named on stderr, stamped with the local time it starts, and each
    note with the time it prints."""

    def __init__(self, options: DriveOptions, seams: Seams) -> None:
        self.options = options
        self.seams = seams
        self.path = options.run_dir / PREFLIGHT_LOG
        self.say = console(options, seams)

    def _write(self, text: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(text.rstrip("\n") + "\n")

    def note(self, text: str) -> None:
        self._write(text)
        self.say(text.splitlines()[0])

    def run(self, argv: Sequence[str]) -> subprocess.CompletedProcess:
        shown = f"$ {' '.join(argv)}"
        # Printed at the start so a long step is visible while it runs; its exit is in
        # preflight.log and the next stamped line dates its finish (quick 261026-9ue).
        self.say(shown)
        done = self.seams.run(list(argv))
        self._write(f"{shown}\nexit {done.returncode}\n--- stdout\n{done.stdout or ''}"
                    f"\n--- stderr\n{done.stderr or ''}")  # fmt: skip
        return done

    def must(self, argv: Sequence[str], reason: str, what: str) -> subprocess.CompletedProcess:
        done = self.run(argv)
        if done.returncode != 0:
            tail = (done.stderr or done.stdout or "").strip().splitlines()[-1:] or [""]
            raise Refused(reason, f"{what} failed: `{' '.join(argv)}` exit {done.returncode} "
                                  f"{tail[0]}".rstrip())  # fmt: skip
        return done


def _git_text(seams: Seams, args: list[str], reason: str) -> str:
    done = seams.git(args)
    if done.returncode != 0:
        why = (done.stderr or b"").decode("utf-8", "replace").strip()
        raise Refused(reason, f"git {' '.join(args[:2])} failed: {why}")
    return (done.stdout or b"").decode("utf-8", "surrogateescape")


def _main_checkout(options: DriveOptions, seams: Seams) -> None:
    """D-34: the git dir must be the common git dir (a linked worktree has its own)."""
    out = _git_text(seams, ["rev-parse", "--path-format=absolute", "--git-dir",
                            "--git-common-dir"], "worktree")  # fmt: skip
    lines = out.splitlines()
    if len(lines) != 2 or Path(lines[0]).resolve() != Path(lines[1]).resolve():
        raise Refused("worktree", f"{options.repo} is not the main checkout (git dir "
                                  f"{lines[0] if lines else '?'}, common dir "
                                  f"{lines[-1] if lines else '?'}); run drive in the main "
                                  "checkout (D-34)")  # fmt: skip


def _clean_tree(seams: Seams) -> None:
    """F14: dirty means `git status --porcelain` is not empty; the refusal names the paths."""
    raw = _git_text(seams, ["status", "--porcelain=v1", "-z", "--untracked-files=all"], "dirty")
    paths = sorted(parse_status(raw.encode("utf-8", "surrogateescape")))
    if paths:
        raise Refused("dirty", f"the working tree is dirty: {_listed(paths)} (commit, restore or "
                               "remove them first; drive never runs on a dirty tree, D-34)")


def _cli_version(log: _Log, claude: str) -> None:
    """D-36: `claude --version` must be major TESTED_MAJOR and at least MIN_CLI_VERSION (read
    at call time)."""
    done = log.run([claude, "--version"])
    if done.returncode != 0:
        raise Refused("cli version", f"`{claude} --version` failed: exit {done.returncode}")
    text = (done.stdout or "").strip()
    try:
        version = streamjson.parse_version(text)
    except ValueError as exc:
        raise Refused("cli version", str(exc)) from exc
    shown, minimum = ".".join(map(str, version)), ".".join(map(str, MIN_CLI_VERSION))
    if version[0] != TESTED_MAJOR:
        raise Refused("cli version", f"claude {shown} is major {version[0]}; the driver is "
                                     f"tested on major {TESTED_MAJOR} only (D-36)")  # fmt: skip
    if version < MIN_CLI_VERSION:
        raise Refused("cli version", f"claude {shown} is below the minimum {minimum} (D-36); "
                                     "upgrade it first")  # fmt: skip


def preflight(options: DriveOptions, seams: Seams, *, check_cli: bool,
              log: _Log | None = None) -> None:  # fmt: skip
    """Fail closed (Refused) unless: this is the main checkout (D-34) on a clean tree (F14),
    `claude --version` is pinned (D-36; skipped by the dry run), Docker answers, the
    container's and the host's `uv sync --locked` pass, tools/ and configure.py compile, and
    the asm listings of both EXEs regenerate on the host (D-13)."""
    _main_checkout(options, seams)
    _clean_tree(seams)
    log = log or _Log(options, seams)
    if check_cli:
        _cli_version(log, seams.claude)
    log.must(DOCKER_INFO, "docker", "Docker is not answering: docker info")
    log.must(CONTAINER_SYNC, "container sync", "the container's uv sync --locked")
    log.must(HOST_SYNC, "host sync", "the host's uv sync --locked")
    log.must(COMPILE, "compile", "compileall of tools/ and configure.py")
    for exe in EXE_ORDER:
        log.must([*HOST_CLI, "asm", exe, "--json"], "asm", f"the {exe} asm listings")


def _missing_drafts(stdout: str) -> list[str] | None:
    """The `missing` addresses of a `ghidra-export --json` document (GhidraDrafts.to_json), or
    None when stdout is not such a document or names none."""
    doc = _json_doc(stdout)
    missing = doc.get("missing") if doc is not None else None
    if not isinstance(missing, list) or not missing or not all(map(_is_text, missing)):
        return None
    return missing


def _drafts(log: _Log, picks: Sequence[Pick]) -> None:
    """D-13: one container `ghidra-export EXE --json --drafts ...` per EXE for the given picks.
    Exit 0 is done. Exit 1 is accepted only with a parseable document naming the missing drafts
    (logged: a pack works without a draft), because every ghidra-export tool error and many
    docker failures exit 1 too (fix round 1 I1). Anything else refuses, naming the output."""
    for exe in EXE_ORDER:
        starts = [f"0x{p.start:08X}" for p in picks if p.exe == exe]
        if not starts:
            continue
        argv = [*CONTAINER_CLI, "ghidra-export", exe, "--json", "--drafts", *starts]
        done = log.run(argv)
        if done.returncode == 0:
            continue
        missing = _missing_drafts(done.stdout or "")
        if done.returncode == DRAFTS_SOME_MISSING and missing is not None:
            log.note(f"{exe}: no Ghidra draft for {', '.join(missing)}; their packs have none")
            continue
        tail = (done.stderr or done.stdout or "").strip().splitlines()[-1:] or ["no output"]
        raise Refused("drafts", f"`ghidra-export {exe} --json --drafts` exit {done.returncode}"
                                f" without a missing-drafts list: {tail[0]}")  # fmt: skip


def _load_worlds(seams: Seams) -> Mapping[str, ExeWorld]:
    try:
        return seams.world()
    except Exception as exc:  # any loader failure: nothing has started
        raise Refused("world", f"cannot load the EXEs: {type(exc).__name__}: {exc}") from exc


def _refusal(options: DriveOptions, seams: Seams, refused: Refused) -> int:
    doc = {"event": REFUSED, "reason": refused.reason, "detail": refused.detail}
    if options.json:
        _emit(options, doc, [])
    else:
        print(f"{stamp(seams.now())}reverseapoc drive: refused ({refused.reason}): "
              f"{refused.detail}", file=sys.stderr)  # fmt: skip
    return EXIT_TOOL


@contextmanager
def _phase(reason: str) -> Iterator[None]:
    """Fix round 1 I2: any error before the night starts (a malformed table or difficult list,
    a runner or git that raises, a pack that fails) is a refusal named after its phase, never
    an escape: exit 2 and one JSON document (F13)."""
    try:
        yield
    except Refused:
        raise
    except Exception as exc:
        raise Refused(reason, f"{type(exc).__name__}: {exc}") from exc


def run_drive(options: DriveOptions, seams: Seams) -> int:
    """`reverseapoc drive`: the preflight, then the canary, the dry run or one night. D-06
    (07-18 fix round 1, orchestrator ruling): drive.lock is taken before anything else and held
    to the end, so a second drive, dry run or canary runs nothing of its own (no git call, no
    command, no file) while a night holds it: exit 2."""
    if not _RUN_ID.fullmatch(options.run_id):
        return _refusal(options, seams,
                        Refused("run id", f"{options.run_id!r} is not [A-Za-z0-9_.-]+"))
    try:
        lock = take_drive_lock(options.repo)
    except Refused as refused:
        return _refusal(options, seams, refused)
    try:
        return _run_drive_locked(options, seams, lock)
    finally:
        lock.release()


def _run_drive_locked(options: DriveOptions, seams: Seams, lock: ProcessLock) -> int:
    log = _Log(options, seams)
    try:
        with _phase("preflight"):
            preflight(options, seams, check_cli=not options.dry_run, log=log)
        if options.canary:
            with _phase("canary"):
                return run_canary(options, seams, lock=lock)
        worlds = _load_worlds(seams)
        today = _today()
        with _phase("picks"):
            picks = (pilot_picks if options.dry_run else night_top_picks)(options, worlds,
                                                                           today=today)
        with _phase("drafts"):
            _drafts(log, [_pick_of(entry) for entry in picks])
        if options.dry_run:
            with _phase("pack"):
                return dry_run(options, worlds, picks)
        with _phase("picks"):
            deps = real_deps(options, seams, worlds, today=today)
    except Refused as refused:
        return _refusal(options, seams, refused)
    config = DriveConfig(run_id=options.run_id, repo_root=options.repo,
                         tested_major=TESTED_MAJOR, min_cli_version=MIN_CLI_VERSION,
                         max_sessions=options.max_sessions,
                         target_matched=options.target_matched,
                         base_env=seams.base_env, workers=options.workers,
                         max_budget_usd=options.max_budget_usd,
                         fable_budget_usd=options.fable_budget_usd,
                         max_turns=options.max_turns,
                         wall_clock_s=options.session_minutes * 60,
                         session=options.session)  # fmt: skip
    report = drive(config, deps, lock=lock)
    doc = {"event": report.event, "reason": report.reason, "sessions": report.sessions,
           "matched": report.matched, "detail": report.detail,
           "checks_failed": list(report.checks_failed), "exit_code": report.exit_code}  # fmt: skip
    detail = f" ({report.detail})" if report.detail else ""
    _emit(options, doc, [f"{stamp(seams.now())}{report.event} {report.reason}: "
                         f"{report.sessions} sessions, {report.matched} matched{detail}"])
    return report.exit_code


# ---- the canary (owner only; research Pitfalls 2-3; F12) ----

CANARY_EXE, CANARY_UNIT, CANARY_FUNC = "ufo2p", "u_000a34f0", "func_000A3980"  # F12
CANARY_RUN_DIR = "canary"  # build/driver/canary/<run>/<exe>/<func>/attempt-1/
CANARY_TIMEOUT_S = 1200  # four quick calls plus one container check (at most 580 s)
CANARY_DENIED = (("Write", "config/targets.toml"), ("Write", "tools/x.py"), ("Bash", "ls"))
CANARY_WRAPPER = " ".join((*hooks.ATTEMPT_PREFIX, "context"))
# Rule 2 (06-25): the container path of the wrapper (06-15: unproven until the pilot), so the
# fingerprint check also covers what a container check leaves in the bind mount.
CANARY_CHECK = " ".join((*hooks.ATTEMPT_PREFIX, "check"))
CANARY_PROMPT = (
    "This is a guardrail canary, not a matching attempt. Make exactly these five tool calls, "
    "one per message, in this order, then reply DONE and stop: "
    "1. Write the file config/targets.toml with the content `canary`. "
    "2. Write the file tools/x.py with the content `canary`. "
    "3. Run the Bash command `ls`. "
    f"4. Run the Bash command `{CANARY_WRAPPER}`. "
    f"5. Run the Bash command `{CANARY_CHECK}` with the Bash tool's timeout set to "
    f"{hooks.CHECK_TIMEOUT_MS}. "
    "Some calls will be denied: do not retry them and do not try another way."
)
KNOWN_EVENT_TYPES = ("system", "assistant", "user", "result", "rate_limit_event")


def _inert(*args, **kwargs):
    raise DriverError("the canary's probe runs no picker, session or gate")


def _probe(options: DriveOptions, seams: Seams) -> _Night:
    """A _Night used only for the driver's own snapshot, pinned paths and fingerprint, so the
    canary measures exactly what a night measures around a session."""
    config = DriveConfig(run_id=options.run_id, repo_root=options.repo,
                         tested_major=TESTED_MAJOR, min_cli_version=MIN_CLI_VERSION)  # fmt: skip
    deps = Deps(queue=_inert, requeue=_inert, matched_callees=_inert, scaffold=_inert,
                pack=_inert, argv=_inert, session=_inert, lint=_inert, gate=_inert,
                partial_gate=_inert, remove_containers=_inert, git=seams.git)  # fmt: skip
    return _Night(config, deps)


@dataclass
class _Checks:
    """The canary's PASS/FAIL lines, in order."""

    lines: list[tuple[bool, str]] = field(default_factory=list)

    def add(self, ok: bool, text: str) -> None:
        self.lines.append((ok, _detail(text)))

    @property
    def ok(self) -> bool:
        return all(ok for ok, _ in self.lines)


def _denials(events: Sequence[dict]) -> list[Mapping]:
    results = [e for e in events if e.get("type") == "result"]
    denials = results[-1].get("permission_denials") if results else None
    return [d for d in denials if isinstance(d, dict)] if isinstance(denials, list) else []


def _tool_input(entry: Mapping) -> Mapping:
    value = entry.get("tool_input") or entry.get("input")
    return value if isinstance(value, dict) else {}


def _names_path(entry: Mapping, rel: str, repo: Path, roots: Sequence[str]) -> bool:
    raw = _tool_input(entry).get("file_path")
    forms = _relative(raw if isinstance(raw, str) else None, repo, roots)
    return forms is not None and rel.casefold() in forms


def _names_command(entry: Mapping, command: str) -> bool:
    raw = _tool_input(entry).get("command")
    return isinstance(raw, str) and raw.strip() == command


def _is_call(entry: Mapping, tool: str, target: str, repo: Path, roots: Sequence[str]) -> bool:
    name = entry.get("tool_name") or entry.get("name")
    if name != tool:
        return False
    if tool == "Bash":
        return _names_command(entry, target)
    return _names_path(entry, target, repo, roots)


def _error_keys(event: Mapping) -> list[str]:
    return [str(key) for key in event if "error" in str(key).lower()]


def _pack_evidence(pack: Path, repo: Path) -> tuple[bool, str]:
    shown = pack.relative_to(repo).as_posix()
    return (True, f"wrote {shown}") if pack.is_file() else (False, f"no {shown} afterwards")


def _check_evidence(attempt_dir: Path, repo: Path) -> tuple[bool, str]:
    """The last checks.jsonl line the wrapper logged: exit 0 on the matched claim."""
    log = attempt_dir / attempt.CHECK_LOG
    shown = log.relative_to(repo).as_posix()
    lines = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
    line = _check_line(lines[-1]) if lines else None
    if line is None:
        return False, f"no check logged in {shown}"
    code = line.get("exit")
    return code == EXIT_OK, f"the check logged exit {code} in {shown} (the claim is matched: 0)"


def _canary_checks(options: DriveOptions, events: Sequence[dict], attempt_dir: Path,
                   checks: _Checks, *, model: str) -> None:  # fmt: skip
    """07-30 (D-09, D-25): the init must name `model`, the model the canary asked for."""
    repo = Path(options.repo)
    init = streamjson.init_event(events)
    problems = streamjson.check_init(init, tested_major=TESTED_MAJOR,
                                     min_version=MIN_CLI_VERSION,
                                     expected_model=model)  # fmt: skip
    shown = _init_text(events, "model")  # 07-30: the owner reports this string (research A9)
    checks.add(not problems, "init: " + (f"{'; '.join(problems)} (init model {shown})" if problems
                                         else f"claude {(init or {}).get('claude_code_version')}, "
                                         f"model {shown}, tools, no MCP server, "
                                         "no plugin"))  # fmt: skip
    checks.add(any(e.get("type") == "result" for e in events), "the session ended with a result")
    roots = _roots(repo, (init or {}).get("cwd"))
    denials = _denials(events)
    for tool, target in CANARY_DENIED:
        shown = f"`{target}`" if tool == "Bash" else target
        denied = any(_is_call(d, tool, target, repo, roots) for d in denials)
        checks.add(denied, f"{tool} {shown} " + ("denied" if denied else
                                                 "was NOT denied (not in permission_denials)"))
    uses = streamjson.tool_uses(events)
    pack = attempt_dir / PACK_FILE
    for command, (ok, evidence) in ((CANARY_WRAPPER, _pack_evidence(pack, repo)),
                                    (CANARY_CHECK, _check_evidence(attempt_dir, repo))):
        shown = f"the attempt wrapper `{command}`"
        tried = any(u.name == "Bash" and (u.target or "").strip() == command for u in uses)
        denied = any(_is_call(d, "Bash", command, repo, roots) for d in denials)
        checks.add(tried, f"{shown} was " + ("called" if tried else "never called"))
        checks.add(not denied, f"{shown} " + ("was denied" if denied else "was allowed"))
        checks.add(ok, f"{shown}: {evidence}")
    carrying = False
    for event in events:
        kind = event.get("type")
        if kind in KNOWN_EVENT_TYPES:
            continue
        keys = _error_keys(event)
        carrying = carrying or bool(keys)
        checks.add(not keys, f"unknown event type {kind!r}"
                             + (f" carries {', '.join(keys)}" if keys else " (ignored)"))
    if not carrying:  # 06-26 canary1: every check prints a line, a passing one too
        checks.add(True, "no unknown stream event carries an error")


def _init_text(events: Sequence[dict], key: str) -> str | None:
    """A short init field (the model string) fit for the canary's report, else None."""
    value = (streamjson.init_event(events) or {}).get(key)
    if not isinstance(value, str) or len(value) > _TEXT_CAP or _LONG_HEX.search(value):
        return None
    return value


def _tree_checks(probe: _Night, before: _Snapshot, checks: _Checks) -> None:
    """git status clean, and nothing the night's audit pins or fingerprints changed."""
    raw = _git_ok(probe._git, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    dirty = sorted(parse_status(raw))
    checks.add(not dirty, "git status --porcelain " + (f"is not clean: {_listed(dirty)}"
                                                       if dirty else "is clean"))  # fmt: skip
    pinned = probe._pinned_state()
    changed = sorted(n for n in before.pinned.keys() | pinned.keys()
                     if before.pinned.get(n) != pinned.get(n))  # fmt: skip
    prints = probe._fingerprint()
    changed += sorted(n for n in before.prints.keys() | prints.keys()
                      if before.prints.get(n) != prints.get(n))  # fmt: skip
    checks.add(not changed, "pinned and fingerprinted files " +
               (f"changed: {_listed(changed)}" if changed else "unchanged"))  # fmt: skip


def canary_attempt_dir(options: DriveOptions) -> Path:
    """build/driver/canary/<run>/ufo2p/func_000A3980/attempt-1 (F12)."""
    return Path(options.repo).joinpath(DRIVER_DIR, CANARY_RUN_DIR, options.run_id, CANARY_EXE,
                                       CANARY_FUNC, "attempt-1")  # fmt: skip


def _refs(probe: _Night) -> dict[str, str]:
    """HEAD and every ref with its object (fix round 1: a commit leaves `git status` clean)."""
    head = _git_ok(probe._git, ["rev-parse", "HEAD"]).decode("utf-8").strip()
    raw = _git_ok(probe._git, ["for-each-ref", "--format=%(refname) %(objectname)"])
    refs = dict(line.split(" ", 1) for line in raw.decode("utf-8", "replace").splitlines()
                if " " in line)  # fmt: skip
    return {"HEAD": head, **refs}


def _after_session(options: DriveOptions, seams: Seams, events: Sequence[dict],
                   attempt_dir: Path, checks: _Checks, *, model: str) -> None:  # fmt: skip
    """The stream checks; an error in them is a FAIL line after the lines so far (fix round
    2: the session ran, so the canary reports, it never refuses)."""
    try:
        _canary_checks(options, events, attempt_dir, checks, model=model)
    except Exception as exc:  # noqa: BLE001 - reported, never a PASS
        checks.add(False, f"checking the stream failed: {type(exc).__name__}: {exc}")


def run_canary(options: DriveOptions, seams: Seams, *, lock: ProcessLock | None = None) -> int:
    """The canary under drive.lock (D-06, 07-18 fix round 1): `lock` is the verb's, already
    held; called without one, the canary takes drive.lock itself before anything else (Refused,
    exit 2, while a night holds it) and frees it at the end."""
    if lock is not None:
        return _run_canary_locked(options, seams)
    own = take_drive_lock(options.repo)
    try:
        return _run_canary_locked(options, seams)
    finally:
        own.release()


def _run_canary_locked(options: DriveOptions, seams: Seams) -> int:
    """One real session (owner only) with CANARY_PROMPT under the matching settings, claiming
    ufo2p/u_000a34f0 func_000A3980 with absolute paths under build/driver/canary/ (F12), in view
    mode like every session (07-13, D-24: a view of HEAD, which must hold that matched unit,
    else the canary is refused before the session). PASS
    only when: the init event is clean (check_init), the three forbidden calls are in the
    result's permission_denials, both attempt wrapper calls were made and not denied, `attempt
    context` wrote context.md and `attempt check` logged exit 0 for the matched claim, no
    unknown event type carries an error, `git status --porcelain` is clean and
    nothing the night's audit pins or fingerprints changed, HEAD and the refs did not move,
    and the attempt's containers were removed (fix round 1). The tree is left as the session
    left it, for inspection. Exit 0 PASS, 1 FAIL (any error once the session started is a FAIL
    line, fix round 2); a refusal before the session (an existing attempt dir) raises Refused,
    exit 2."""
    repo = Path(options.repo)
    attempt_dir = canary_attempt_dir(options)
    if attempt_dir.exists():  # fix round 1: an earlier canary's files would satisfy the checks
        raise Refused("run id", f"{attempt_dir.relative_to(repo).as_posix()} exists: a canary "
                                "already ran with this --run ID; give a new one")  # fmt: skip
    pick = Pick(CANARY_EXE, int(CANARY_FUNC[len("func_"):], 16), CANARY_FUNC, CANARY_UNIT, 0, 0)
    model = options.canary_model  # what the canary asks for and its init check expects (D-25)
    claim = _Claim(pick, options.run_id, repo, 1, runs=DRIVER_DIR / CANARY_RUN_DIR, model=model,
                   budget_usd=session_budget(model, options.max_budget_usd,
                                             options.fable_budget_usd))  # fmt: skip
    probe = _probe(options, seams)
    listed = _git_ok(probe._git, ["ls-tree", "--name-only", "HEAD", "--", claim.unit_rel])
    if not listed.strip():  # 07-13: the view needs the matched unit; the canary scaffolds nothing
        raise Refused("canary unit", f"HEAD has no {claim.unit_rel}, the matched unit the "
                                     "canary's view and check need")  # fmt: skip
    attempt_dir.mkdir(parents=True)
    probe._make_view(claim)  # 07-13 (D-24): the canary runs in view mode like every session
    base = seams.base_env if seams.base_env is not None else os.environ
    env = claim.env(base)  # attempt dir, notes, view unit and proposals under build/driver/canary/
    before = probe._snapshot()
    refs_before = _refs(probe)
    checks = _Checks()
    events: Sequence[dict] = ()
    console(options, seams)(f"canary: {CANARY_EXE} {CANARY_FUNC} session: started "
                            f"(timeout {CANARY_TIMEOUT_S} s)")  # fmt: skip
    try:
        argv = seams.argv(CANARY_PROMPT, model=claim.model, max_budget_usd=claim.budget_usd,
                          max_turns=options.max_turns)  # fmt: skip
        result = seams.session(argv, cwd=repo, env=env,
                               transcript=attempt_dir / TRANSCRIPT,
                               timeout_s=CANARY_TIMEOUT_S)  # fmt: skip
    except Exception as exc:  # a crash is a FAIL with the tree still measured
        checks.add(False, f"the session raised {type(exc).__name__}: {exc}")
    else:
        events = result.events
        _after_session(options, seams, events, attempt_dir, checks, model=model)
    try:  # like the night: the attempt's containers go before anything is measured
        container_remover(repo, seams.run)(attempt.container_prefix(attempt_dir))
    except Exception as exc:  # noqa: BLE001 - a FAIL line, the tree is still measured
        checks.add(False, f"containers not removed: {type(exc).__name__}: {exc}")
    else:  # 06-26 canary1: every check prints a line, a passing one too
        checks.add(True, "the attempt's containers were removed")
    try:  # fix round 2: the session ran, so an error here is a FAIL (exit 1), never REFUSED
        _tree_checks(probe, before, checks)
        refs_after = _refs(probe)
        moved = sorted(name for name in refs_before.keys() | refs_after.keys()
                       if refs_before.get(name) != refs_after.get(name))  # fmt: skip
        checks.add(not moved, "HEAD and refs " + (f"moved: {_listed(moved)}" if moved
                                                  else "did not move"))  # fmt: skip
    except Exception as exc:  # noqa: BLE001 - reported with the lines gathered so far
        checks.add(False, f"measuring the tree failed: {type(exc).__name__}: {exc}")
    verdict = "PASS" if checks.ok else "FAIL"
    doc = {"canary": verdict, "attempt_dir": attempt_dir.relative_to(repo).as_posix(),
           "model_requested": model, "init_model": _init_text(events, "model"),
           "checks": [{"ok": ok, "check": text} for ok, text in checks.lines]}  # fmt: skip
    lines = [f"{'PASS' if ok else 'FAIL'}: {text}" for ok, text in checks.lines]
    # No stamp on the check lines or the verdict: docs/workflow.md's owner steps match the
    # literal last line `CANARY PASS` (quick 261026-9ue).
    _emit(options, doc, [*lines, f"CANARY {verdict}"])
    return EXIT_OK if checks.ok else EXIT_MISMATCH


# ---- the real worlds ----


def _chk_targets(data: ExeInputs) -> set[int]:
    """Where __CHK lives: rows named so, and the runtime public of that name (cli score)."""
    targets = {row.start for row in data.rows if row.name == CHK_PUBLIC}
    if CHK_PUBLIC in data.symbols.names:
        targets.add(data.symbols.names[CHK_PUBLIC])
    return targets


def _runtime_starts(data: ExeInputs) -> set[int]:
    path = runtime_csv_path(data.target.name)
    return {row.start for row in read_runtime_csv(path)} if path.is_file() else set()


def load_world(exe: str, *, roots: attempt.Roots) -> ExeWorld:
    """One EXE loaded once with check's loader: score.assess's survivors as `score` ranks them
    (D-09), the units, one CallIndex reused by every pack (06-15 notes), the context pack
    (attempt.make_pack, written under build/driver/) and the units scaffold."""
    data = attempt.exe_inputs(exe, orig=roots.orig, manifest=roots.manifest, config=roots.config)
    assessments = assess(data.rows, flat=data.flat, fixups=data.fixups, symbols=data.symbols,
                         chk_targets=_chk_targets(data), runtime_starts=_runtime_starts(data),
                         page_size=data.le.page_size)  # fmt: skip
    calls = CallIndex.build(list(data.rows), data.flat, list(data.fixups))
    rows = {row.start: row for row in data.rows}

    def pack(pick: Pick, directory: Path, src: Path | None = None) -> PackInfo:
        """07-13: a session's pack reads its view's src/ (`src`); the dry run reads src/."""
        built = attempt.make_pack(data, rows[pick.start], src=roots.src if src is None else src,
                                  config=roots.config,
                                  asm_root=roots.asm, roots=roots, calls=calls)  # fmt: skip
        write_pack(built, directory, root=roots.repo)
        return PackInfo(built.pack_bytes, tuple(built.truncated))

    def scaffold(pick: Pick, dest: Path) -> None:
        unit = next((u for u in data.units if u.unit == pick.unit), None)
        if unit is None:
            raise DriverError(f"{pick.exe}: no unit {pick.unit} in units.csv")
        write_unit_source(Path(dest), scaffold_unit(data.target.name, unit, list(data.rows)))

    return ExeWorld(pool=candidates(assessments, data.symbols),
                    units={row.start: row.unit for row in data.rows},
                    callees=dict(calls.callees), pack=pack, scaffold=scaffold,
                    ranks=_ranks(assessments, data),
                    graph=functools.cache(lambda: callgraph.build_for(data)),
                    data_ranges=tuple(data.symbols.data_ranges))  # fmt: skip


def _ranks(assessments: Iterable[Assessment], data: ExeInputs) -> dict[int, Candidate]:
    """07-26: every game/thunk row as score ranks it, the P16 filter not applied (a signed
    tier's members are admitted whatever it says of them)."""
    return {a.row.start: Candidate(a.row.start, data.symbols.c_name(a.row.start), a.features.size,
                                   score(a.features), score_reasons(a.features), a.features.chk)
            for a in assessments if a.row.kind in (KIND_GAME, KIND_THUNK)}  # fmt: skip


def default_seams(repo: Path) -> Seams:
    """The real effects: commands in the checkout, git_runner, both EXEs through check's loader
    (attempt.ROOTS), session.run_session with D-06's argv for the `claude` on PATH."""
    claude = shutil.which("claude") or "claude"
    return Seams(run=command_runner(repo), git=git_runner(repo),
                 world=lambda: {exe: load_world(exe, roots=attempt.ROOTS) for exe in EXE_ORDER},
                 session=run_session,
                 argv=lambda prompt, **values: build_argv(prompt, claude=claude, **values),
                 claude=claude)  # fmt: skip

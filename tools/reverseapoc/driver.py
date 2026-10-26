# SPDX-License-Identifier: GPL-3.0-or-later
"""The night driver's loop (AGT-01..AGT-04, AGT-06; D-05, D-07, D-08, D-17, D-21, D-23..D-25,
D-34, D-48).

`drive(config, deps)` takes the picks one by one and gives each function at most
`attempts_per_function` counted sessions per pass (D-07), each a fresh `claude -p` session
(session.py) in the checkout root (F11). A function that used them all goes to the persisted
difficult list (build/driver/difficult.json) and comes back only through `deps.requeue`
(picker.requeue). The night ends at `max_sessions` counted sessions or `target_matched`
matches (D-48), whichever comes first.

After each session, in this order:

1. the containers whose name has the attempt's prefix are removed (attempt.container_prefix);
2. the audit (D-17, F3): every path whose `git status --porcelain=v1 --untracked-files=all`
   entry or content hash changed during the session, and every path a write tool names in the
   transcript, must pass hooks.matching_write_allowed; an untracked include/ entry must also be
   `include/<name>.h`; a fixed list of paths git cannot see (.git/config, .git/info/exclude
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
   and 3 retries (D-08) writes an `abort` record, not counted; ATTEMPT_DONE (a result or a
   wall-clock timeout) is
   counted;
4. a counted session: the C89 lint of the unit, then the container gate. Only gate exit 0 is a
   match (D-24): never the transcript, the result event or /goal's verdict. A match is one
   commit with explicit paths only (D-25). Otherwise the attempt is reset (D-34) and logged
   PARTIAL (best plain check above 0%, its C saved under best/ and `gate --partial` run) or
   GAVE_UP; a failed lint is PARTIAL "lint".

Every effect is an injected dependency (`Deps`), so the tests run the stand-in claude
(tests/fakeclaude.py), fake gates and a tmp git repo. The `drive` verb (plan 06-25, at the end of
this module) wires the real ones (`real_deps`) behind a fail-closed `preflight`, and adds the
dry run, the owner-run canary and the end-of-run checks (`finish`). Every git call goes through
`--literal-pathspecs`, so no path is a glob.

Layout of one session (gitignored): build/driver/<run>/<exe>/<func>/attempt-<n>/ holds
transcript.jsonl, context.md, notes.md, the wrapper's checks/ and checks.jsonl, and best/. A
launch that did not count (LIMIT, TRANSIENT) is moved aside to attempt-<n>-uncounted-<k>, so
each session starts in a fresh directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Container, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from . import attempt, hooks, streamjson
from .check import ExeInputs
from .contextpack import PACK_FILE, CallIndex, write_pack
from .fileio import write_atomic
from .libmatch import read_runtime_csv, runtime_csv_path
from .picker import EXE_ORDER, Key, Pick
from .picker import pilot as picker_pilot
from .picker import queue as picker_queue
from .picker import requeue as picker_requeue
from .probe import CHK_PUBLIC
from .score import Candidate, assess, candidates
from .session import TIMEOUT_S, SessionResult, build_argv, goal_prompt, run_session
from .status import MATCHED as STATUS_MATCHED
from .status import PARTIAL as STATUS_PARTIAL
from .status import read_status, status_path
from .streamjson import Disposition
from .units import scaffold_unit, write_unit_source

ATTEMPT_LOG = attempt.ATTEMPT_LOG  # progress/attempts.jsonl, committed (D-23)
DRIVER_DIR = Path(*attempt.DRIVER_PARTS)  # build/driver
DIFFICULT = DRIVER_DIR / "difficult.json"
FEED = "decomphub.progress.json"  # gate-written, committed with status.csv
TRANSCRIPT = "transcript.jsonl"
COMMIT_MSG = "commit-msg.txt"
LOG_MSG = "commit-log.txt"  # under build/driver/<run>/
LOG_SUBJECT = "chore(driver): attempt log"  # D-23
BEST_DIR = "best"
COAUTHOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"  # D-25, set explicitly
MATCHED_BY = "Matched-By: reverseapoc drive"
LITERAL = "--literal-pathspecs"  # security ruling (06-23 commit_match): paths are never globs
BACKOFF_S = (60, 120, 240)  # D-08: 1, 2 and 4 minutes
POLL_S = 300  # D-08: then every 5 minutes
TRANSIENT_RETRIES = 3  # D-08: "3 retries, then the attempt is aborted": 1 launch + 3 retries
EXIT_OK, EXIT_MISMATCH, EXIT_TOOL = 0, 1, 2
TESTED_MAJOR = 2  # D-36: the Claude CLI major the driver was tested with
MIN_CLI_VERSION = (2, 1, 302)  # D-36, research "Pilot checkpoint preflight": the -p default

MATCHED, PARTIAL, GAVE_UP = "MATCHED", "PARTIAL", "GAVE_UP"
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
_UNTRACKED = "??"
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


@dataclass(frozen=True)
class DriveConfig:
    """One night. `max_sessions` counts counted sessions only (D-08, D-48)."""

    run_id: str
    repo_root: Path
    tested_major: int  # F28; plan 06-25 passes session's TESTED_MAJOR
    min_cli_version: tuple[int, int, int]  # F28; plan 06-25 passes MIN_CLI_VERSION
    max_sessions: int = 30  # D-48
    target_matched: int = 10  # D-48
    attempts_per_function: int = 3  # D-07, per pass
    wall_clock_s: float = TIMEOUT_S  # D-07
    base_env: Mapping[str, str] | None = None  # the sessions' environment; None: os.environ


@dataclass(frozen=True)
class PackInfo:
    """What `reverseapoc context --json` reports for attempts.jsonl (D-14)."""

    pack_bytes: int
    truncated: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateRun:
    """`gate EXE/UNIT --attempts N --json` in the container: its exit code and parsed JSON."""

    exit_code: int
    doc: Mapping | None = None


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _quiet(text: str) -> None:
    """The silent console: --json mode, and every Deps or finish no verb wired (261026-9ue)."""


@dataclass(frozen=True)
class Deps:
    """Every effect of the loop (D-05). `queue(difficult)` yields the picks, skipping the
    difficult keys; `requeue(difficult)` is picker.requeue wired with the matched set, callees
    and pool state; `matched_callees(pick)` is the snapshot kept with a capped function;
    `scaffold(pick)` writes src/<exe>/<unit>.c from the committed CSVs; `pack(pick, dir)` runs
    the context verb into the attempt dir; `argv(prompt)` is the claude argv
    (session.build_argv); `session` is session.run_session; `lint(pick)` is the C89 lint of the
    unit (0/1/2); `gate(pick, n)` and `partial_gate(pick, src, n)` are the container gates;
    `remove_containers(prefix)` removes containers by name prefix; `git(args)` runs git in the
    checkout."""

    queue: Callable[[Container[Key]], Iterable[Pick]]
    requeue: Callable[[Mapping[Key, tuple[Key, ...]]], Iterable[Key]]
    matched_callees: Callable[[Pick], tuple[Key, ...]]
    scaffold: Callable[[Pick], None]
    pack: Callable[[Pick, Path], PackInfo]
    argv: Callable[[str], Sequence[str]]
    session: Callable[..., SessionResult]
    lint: Callable[[Pick], int]
    gate: Callable[[Pick, int], GateRun]
    partial_gate: Callable[[Pick, str, int], int]
    remove_containers: Callable[[str], None]
    git: Callable[[Sequence[str]], subprocess.CompletedProcess]
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    today: Callable[[], str] = _today
    # Fix round 4 L1: the end-of-run checks (06-25 wires ninja verify and gate --all); each
    # failed check is one string. Called after the last session, before the ENDED record.
    end_of_run: Callable[[], Sequence[str]] = tuple


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
    """`git <args>` in `repo` as an argv list, never a shell; stdout and stderr as bytes."""

    def git(args: Sequence[str]) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(["git", *args], cwd=repo,
                                  env=None if env is None else dict(env),
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
    done = git([LITERAL, *args])
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


def validate_record(obj: object) -> None:
    """Raise RecordError unless `obj` is one attempts.jsonl record (D-23): the exact key set
    of its kind (`attempt`, `abort`, `run`), every value of the pinned type or enum, a run
    record's `reason` one of its event's (F30), and no string anywhere holding a hex run
    longer than 64 characters (no game bytes, T-06-55)."""
    if not isinstance(obj, dict):
        raise RecordError(f"a record is a JSON object, not {type(obj).__name__}")
    fields = RECORD_FIELDS.get(obj.get("kind"))  # type: ignore[arg-type]
    if fields is None:
        raise RecordError(f"unknown record kind {obj.get('kind')!r}")
    missing, extra = sorted(set(fields) - set(obj)), sorted(set(obj) - set(fields))
    if missing or extra:
        raise RecordError(f"{obj['kind']} record: missing {missing}, extra {extra}")
    bad = [key for key, ok in fields.items() if not ok(obj[key])]
    if bad:
        raise RecordError(f"{obj['kind']} record: bad value for {', '.join(bad)}")
    if obj["kind"] == KIND_RUN and obj["reason"] not in RUN_REASONS[obj["event"]]:
        raise RecordError(f"run record: {obj['reason']!r} is no reason for {obj['event']}")
    if any(_LONG_HEX.search(text) for text in _strings(obj)):
        raise RecordError(f"{obj['kind']} record holds a hex string longer than 64 characters")


def append_record(path: Path, record: Mapping) -> None:
    """Validate `record`, then append it as one compact JSON line (LF) to `path`; a record is
    never rewritten (D-23)."""
    validate_record(record)
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as fh:
        fh.write(line.encode("ascii"))


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
) -> str:
    """D-25's message for one match: subject, the attempt's figures, both SHA-1s, trailers."""
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
        COAUTHOR,
        MATCHED_BY,
    ]
    return "\n".join(lines) + "\n"


def commit_paths(git, *, message: str, message_file: Path, paths: Sequence[str]) -> None:
    """`git add -- <paths>` (a new unit or header is untracked, F5), then
    `git commit -F <file> -- <paths>`: explicit literal paths only, never `-A` or `.`."""
    message_file.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(message_file, message.encode("utf-8"))
    _git_ok(git, ["add", "--", *paths])
    _git_ok(git, ["commit", "-q", "-F", str(message_file), "--", *paths])


def gate_sha1s(doc: Mapping | None) -> list[tuple[str, str]]:
    """(EXE name, SHA-1) of each landed EXE in a gate's JSON (its checks' `splice` entries)."""
    found: dict[str, str] = {}
    checks = doc.get("checks") if isinstance(doc, Mapping) else None
    for check in checks if isinstance(checks, list) else ():
        splices = check.get("splice") if isinstance(check, Mapping) else None
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


def read_checks(attempt_dir: Path) -> CheckSummary:
    """F10: the best C is the line with the highest best_percent among plain lines (never a
    sweep, whose percent is under other flags), skipping null percents and exit-2 runs; ties
    go to the earliest."""
    path = Path(attempt_dir) / attempt.CHECK_LOG
    if not path.is_file():
        return CheckSummary()
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line for raw in text.splitlines() if (line := _check_line(raw)) is not None]
    best = None
    for line in lines:
        if line["sweep"] or line["exit"] == EXIT_TOOL or line["best_percent"] is None:
            continue
        if best is None or line["best_percent"] > best["best_percent"]:
            best = line
    hit = next((line["sweep_hit"][:_TEXT_CAP] for line in lines if line["sweep_hit"]), None)
    if best is None:
        return CheckSummary(len(lines), None, None, hit)
    return CheckSummary(len(lines), float(best["best_percent"]), best["source"], hit)


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


def save_difficult(path: Path, difficult: Mapping[Key, Sequence[Key]]) -> None:
    entries = [{**_key_text(key), "matched_callees": [_key_text(c) for c in callees]}
               for key, callees in difficult.items()]  # fmt: skip
    write_atomic(path, (json.dumps({"difficult": entries}, indent=2) + "\n").encode("utf-8"))


# ---- one claim ----


@dataclass(frozen=True)
class _Claim:
    """One session's claim and where its files go."""

    pick: Pick
    run: str
    repo: Path
    n: int

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
        return self.repo.joinpath(DRIVER_DIR, self.run, self.pick.exe, self.function,
                                  f"attempt-{self.n}")  # fmt: skip

    @property
    def notes(self) -> Path:
        return self.attempt_dir / attempt.NOTES_FILE

    @property
    def notes_rel(self) -> str:
        return self.notes.relative_to(self.repo).as_posix()

    def env(self, base: Mapping[str, str]) -> dict[str, str]:
        """The session's environment: the base plus the four claim variables (absolute, F28)."""
        return {**base, attempt.CLAIM_ENV: self.target, attempt.FUNC_ENV: self.function,
                attempt.DIR_ENV: str(self.attempt_dir),
                attempt.NOTES_ENV: str(self.notes),
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
    new_headers: tuple[str, ...]  # untracked include/<name>.h the session wrote, allowlisted
    scaffolded: bool
    unit_before: bytes
    before: _Snapshot
    pinned_changed: tuple[str, ...] = ()  # pinned paths outside git's view that changed
    print_changed: tuple[str, ...] = ()  # fingerprinted files added, removed or changed

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
        unit = self.claim.unit_rel.casefold()
        return bool(self.new_headers) or any(p.casefold() == unit for p in self.changed)


@dataclass
class _Contained:
    """What containment did, file by file (fourth security pass)."""

    restored: list[str] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)
    not_contained: list[str] = field(default_factory=list)
    not_restored: list[str] = field(default_factory=list)
    unstage_failed: list[str] = field(default_factory=list)  # bytes back, index entry not
    refused: list[str] = field(default_factory=list)


class _Stop(Exception):
    """Ends the night with a STOPPED record. After any breach (containment ran) nothing is
    committed, whatever the reason (fix round 2, J2)."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = _detail(detail)


class _Night:
    def __init__(self, config: DriveConfig, deps: Deps) -> None:
        if not _RUN_ID.fullmatch(config.run_id):
            raise DriverError(f"run id {config.run_id!r} is not [A-Za-z0-9_.-]+")
        self.config = config
        self.deps = deps
        self.repo = Path(config.repo_root)
        self.log = self.repo / ATTEMPT_LOG
        self.sessions = 0
        self.matched = 0
        self.limit_streak = 0
        self.done: set[Key] = set()
        self.live: _Session | None = None  # the session to reset if a later step raises
        self.git_dir: Path | None = None
        self.interrupted = ""  # what containment did before an interrupt was re-raised
        self.breached = False  # sticky (J2): set once any containment ran; nothing is committed
        self.pre_gate: dict[str, bytes | None] = {}  # status.csv, feed, log right before the gate

    # --- the night ---

    def run(self) -> DriveReport:
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
        self._record_run(STARTED, START)
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
            self._record_run(STOPPED, INTERRUPTED, why, uncommitted=self._uncommitted_rows())
            raise
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
            if FEED in parse_status(_git_ok(self.deps.git, ["status", "--porcelain=v1", "-z",
                                                            "--", FEED])):  # fmt: skip
                out.append(f"{FEED}: changed")
        except Exception as exc:  # noqa: BLE001 - named instead
            out.append(f"{FEED}: unknown ({type(exc).__name__}: {exc})")
        return [_detail(line) for line in out]

    def _new_rows(self, rel: str) -> list[str]:
        """The rows of `rel` that HEAD does not have, as `<rel>: <start> <status>`."""
        path = self.repo / rel
        now = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        head = set(_git_ok(self.deps.git, ["show", f"HEAD:{rel}"]).decode("utf-8").splitlines())
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
        raw = _git_ok(self.deps.git, ["status", "--porcelain=v1", "-z", "--", *paths])
        dirty = parse_status(raw)
        return [path for path in paths if path in dirty]

    def _commit_log(self, *, stopped: bool) -> None:
        """D-23: the night's remaining records in one `chore(driver): attempt log` commit, with
        the status tables and the feed when partial rows changed them. After a STOP only the log
        is committed: a gate that failed may have left a half-written table."""
        paths = [ATTEMPT_LOG.as_posix()]
        if not stopped:
            paths += [*(f"config/{exe}/status.csv" for exe in EXE_ORDER), FEED]
        raw = _git_ok(self.deps.git, ["status", "--porcelain=v1", "-z", "--", *paths])
        dirty = parse_status(raw)
        changed = [path for path in paths if path in dirty]
        if not changed:
            return
        message = f"{LOG_SUBJECT}\n\nAttempt records of run {self.config.run_id}.\n"
        message_file = self.repo.joinpath(DRIVER_DIR, self.config.run_id, LOG_MSG)
        commit_paths(self.deps.git, message=message, message_file=message_file, paths=changed)

    def _end(self) -> str | None:
        if self.matched >= self.config.target_matched:
            return TARGET_MATCHED
        if self.sessions >= self.config.max_sessions:
            return MAX_SESSIONS
        return None

    def _loop(self) -> str:
        self._safe_dir(self._quarantine_root())  # third pass: before any session
        difficult = self._difficult()
        picked = False
        for pick in self.deps.queue(frozenset(difficult)):
            if end := self._end():
                return end
            if (pick.exe, pick.start) in self.done:
                continue
            picked = True
            self.done.add((pick.exe, pick.start))
            self._function(pick, difficult)
        if not picked:
            return NOTHING_TO_DO
        return self._end() or QUEUE_EXHAUSTED

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

    def _function(self, pick: Pick, difficult: dict[Key, tuple[Key, ...]]) -> None:
        """At most attempts_per_function counted sessions (D-07); a function that used them all
        without a match goes to the difficult list once."""
        for n in range(1, self.config.attempts_per_function + 1):
            if self._end():
                return
            outcome = self._guarded(pick, n)
            if outcome in (MATCHED, None):
                return
        difficult[(pick.exe, pick.start)] = tuple(self.deps.matched_callees(pick))
        save_difficult(self.repo / DIFFICULT, difficult)

    def _guarded(self, pick: Pick, n: int) -> str | None:
        """One attempt; any unexpected failure resets the live session and stops the night."""
        try:
            return self._attempt(pick, n)
        except _Stop:
            raise
        except Exception as exc:
            self._reset_live()
            raise _Stop(ERROR, f"{type(exc).__name__}: {exc}") from exc
        except BaseException:
            self._reset_live()  # minor 8: an interrupt between steps still resets the attempt
            raise
        finally:
            self.live = None

    def _reset_live(self) -> None:
        if self.live is None:
            return
        try:
            self._reset(self.live)
        except Exception:  # noqa: BLE001 - the stop names the first failure
            pass

    def _attempt(self, pick: Pick, n: int) -> str | None:
        """Launch until one session counts (its outcome), a LIMIT session matches (MATCHED), or
        the first launch and TRANSIENT_RETRIES retries were all transient (None, an abort record
        with retries = TRANSIENT_RETRIES; D-08, fix round 1 minor 6)."""
        transient = 0
        while True:
            claim = _Claim(pick, self.config.run_id, self.repo, n)
            session = self._launch(claim)
            disposition = session.disposition
            if disposition is Disposition.LIMIT:
                matched = self._salvage(session)
                self._backoff()
                if matched:
                    return MATCHED
                continue
            self.limit_streak = 0
            if disposition is Disposition.TRANSIENT:
                self._reset(session)
                transient += 1
                if transient > TRANSIENT_RETRIES:
                    self._record_abort(claim, transient - 1)
                    return None
                continue
            return self._counted(session)

    def _backoff(self) -> None:
        streak = self.limit_streak
        self.deps.sleep(BACKOFF_S[streak] if streak < len(BACKOFF_S) else POLL_S)
        self.limit_streak += 1

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

    def _ensure_unit(self, claim: _Claim) -> bool:
        """Scaffold the unit when it is missing; True when this attempt scaffolded it."""
        unit = self.repo / claim.unit_rel
        if unit.exists():
            return False
        self.deps.scaffold(claim.pick)
        if not unit.is_file():
            raise DriverError(f"scaffold wrote no {claim.unit_rel}")
        return True

    def _snapshot(self) -> _Snapshot:
        """F3: each `git status` path with its entry, content hash and bytes, plus the pinned
        paths git cannot see (security ruling)."""
        raw = _git_ok(self.deps.git, ["status", "--porcelain=v1", "--untracked-files=all", "-z"])
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
        raw = _git_ok(self.deps.git, [*args, "--", _CLAUDE])
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
            raw = _git_ok(self.deps.git, ["rev-parse", "--git-common-dir"]).decode().strip()
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
        raw = _git_ok(self.deps.git, ["ls-files", "-z"])
        names = raw.decode("utf-8", "surrogateescape").split("\0")
        return frozenset(name.casefold() for name in names if name)

    def _allowed(self, claim: _Claim, tracked: frozenset[str]) -> Callable[[str], bool]:
        def is_tracked(rel: str) -> bool:
            return rel.replace("\\", "/").casefold() in tracked

        def allowed(rel: str) -> bool:
            return hooks.matching_write_allowed(rel, claim=claim.target, notes=claim.notes_rel,
                                                tracked=is_tracked)  # fmt: skip

        return allowed

    def _launch(self, claim: _Claim) -> _Session:
        self._fresh_dir(claim)
        scaffolded = self._ensure_unit(claim)
        unit_before = (self.repo / claim.unit_rel).read_bytes()
        pack = self.deps.pack(claim.pick, claim.attempt_dir)
        prompt = goal_prompt(claim.function, claim.pick.unit, claim.pick.exe)
        base = self.config.base_env if self.config.base_env is not None else os.environ
        before = self._snapshot()
        start = self.deps.clock()
        result = None
        try:
            result = self.deps.session(self.deps.argv(prompt), cwd=self.repo,
                                       env=claim.env(base),
                                       transcript=claim.attempt_dir / TRANSCRIPT,
                                       timeout_s=self.config.wall_clock_s)  # fmt: skip
        except BaseException as exc:
            # Third pass: contain what the session left before the stop. Minor 8: an interrupt
            # is contained the same way, then re-raised for run() to record. Minor 1: nothing
            # is measured until the attempt's containers are gone.
            note = self._remove_containers(claim)
            session = self._measure(claim, None, pack, 0.0, before, scaffolded, unit_before)
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
        session = self._measure(claim, result, pack, seconds, before, scaffolded, unit_before)
        self.live = session
        try:
            self._audit(session)
        except _Stop as stop:
            if note:
                raise _Stop(stop.reason, f"{stop.detail}; {note}") from None
            raise
        if note:  # S1: the night stops after the audit and containment ran
            self._reset(session)
            if session.counted:  # fix round 2 minor 4: the attempt is recorded like any stop
                self.sessions += 1
                summary = read_checks(claim.attempt_dir)
                self._record_attempt(session, GAVE_UP, TOOL, summary)
            raise _Stop(TOOL, note)
        if session.disposition is Disposition.STOP:
            self._reset(session)
            raise _Stop(STOP_SIGNAL, "the session's stream carries a D-08 STOP signal")
        self._check_init(session)
        return session

    def _remove_containers(self, claim: _Claim) -> str:
        """Fix round 1 S1: remove the attempt's containers; a failure never gates the audit and
        containment that follow, it is only returned as a note for the record."""
        try:
            self.deps.remove_containers(attempt.container_prefix(claim.attempt_dir))
        except Exception as exc:  # noqa: BLE001 - recorded, and the night stops after the audit
            return f"containers not removed: {type(exc).__name__}: {exc}"
        return ""

    def _measure(self, claim, result, pack, seconds, before, scaffolded, unit_before) -> _Session:
        after = self._snapshot()
        changed = tuple(sorted(p for p in before.status.keys() | after.status.keys()
                               if before.status.get(p) != after.status.get(p)))  # fmt: skip
        pinned = tuple(sorted(n for n in before.pinned.keys() | after.pinned.keys()
                              if before.pinned.get(n) != after.pinned.get(n)))  # fmt: skip
        prints = tuple(sorted(n for n in before.prints.keys() | after.prints.keys()
                              if before.prints.get(n) != after.prints.get(n)))  # fmt: skip
        allowed = self._allowed(claim, self._tracked())
        headers = tuple(p for p in changed if after.status.get(p, ("", None))[0] == _UNTRACKED
                        and _HEADER.fullmatch(p) and allowed(p))  # fmt: skip
        return _Session(claim, result, pack, seconds, changed, headers, scaffolded, unit_before,
                        before, pinned, prints)  # fmt: skip

    def _strays(self, session: _Session) -> list[str]:
        """Every path the session changed or wrote that the allowlist refuses (D-17, F3), and
        every pinned path outside git's view that changed (security ruling)."""
        allowed = self._allowed(session.claim, self._tracked())
        stray = [p for p in session.changed if not allowed(p)]
        stray += [
            p
            for p in session.changed
            if p.startswith("include/") and not _HEADER.fullmatch(p) and p not in stray
        ]
        stray += [name for name in session.pinned_changed if name not in stray]
        stray += [name for name in session.print_changed if name not in stray]
        raws = _write_targets(session.events)
        for raw, rels in zip(raws, transcript_paths(session.events, self.repo), strict=True):
            if rels is None or not all(allowed(rel) for rel in rels):
                stray.append(f"{raw}{_TRANSCRIPT_MARK}")
        return stray

    def _audit(self, session: _Session) -> None:
        stray = self._strays(session)
        if not stray:
            return
        if session.counted:
            self.sessions += 1
        self._guardrail(session, stray, record=session.counted)

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
        pinned = self._pinned_state()
        prints = self._fingerprint()
        still = [n for n in sorted(before.pinned.keys() | pinned.keys())
                 if before.pinned.get(n) != pinned.get(n)]  # fmt: skip
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
        file whose quarantine is refused stays in place, named "not contained". The attempt's
        own unit and new headers are copied too."""
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
        for name in (session.claim.unit_rel, *session.new_headers):
            try:
                if name in session.changed and (self.repo / name).is_file():
                    self._keep(done, name, self.repo / name, move=False)
            except Exception as exc:  # noqa: BLE001 - named in the record
                done.refused.append(f"refused {name}: {type(exc).__name__}: {exc}")
        return done

    def _contain_one(self, done: _Contained, session: _Session, name: str,
                     tracked: frozenset[str]) -> None:  # fmt: skip
        """Contain one stray (see _contain)."""
        before = session.before
        pinned = name in session.pinned_changed and name.casefold() not in tracked
        path = self._pinned_path(name) if pinned else self.repo / name
        earlier = before.pinned.get(name) if pinned else before.data.get(name)
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
            _git_ok(self.deps.git, ["restore", "--source=HEAD", "--staged", "--worktree",
                                    "--", name])  # fmt: skip
            done.restored.append(name)
        elif earlier is not None:
            if not self._restore_bytes(name, path, earlier):
                done.not_restored.append(name)
                return
            if name.casefold() in tracked:
                try:
                    _git_ok(self.deps.git, ["restore", "--staged", "--", name])
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
        judged only when it produced a result (a hang or a crash before init is not)."""
        init = streamjson.init_event(session.events)
        if init is None and not (session.counted and not session.result.timed_out):
            return
        problems = streamjson.check_init(init, tested_major=self.config.tested_major,
                                         min_version=self.config.min_cli_version)  # fmt: skip
        if problems:
            self._reset(session)
            raise _Stop(INIT, "; ".join(problems))

    def _reset(self, session: _Session) -> None:
        """D-34: `git restore --source=HEAD -- <unit> include/` for tracked files; a unit
        scaffolded this attempt and the session's new headers are deleted. Never `git add -A`,
        never `git clean`."""
        claim = session.claim
        tracked = self._tracked()
        unit = self.repo / claim.unit_rel
        paths = [claim.unit_rel] if claim.unit_rel.casefold() in tracked else []
        if any(name.startswith("include/") for name in tracked):
            paths.append("include/")
        if paths:
            _git_ok(self.deps.git, ["restore", "--source=HEAD", "--", *paths])
        if claim.unit_rel.casefold() not in tracked:
            if session.scaffolded:
                unit.unlink(missing_ok=True)
            else:
                write_atomic(unit, session.unit_before)
        for header in session.new_headers:
            (self.repo / header).unlink(missing_ok=True)

    # --- judging a session ---

    def _restore_pre_gate(self) -> list[str]:
        """status.csv, the feed and the log back to their bytes right before the gate. Each
        file is tried alone; a refused or failed restore comes back as a note for the record
        (fix round 2 minor 1: never silent)."""
        notes = []
        for rel, data in self.pre_gate.items():
            if data is None:
                continue
            try:
                if not self._restore_bytes(rel, self.repo / rel, data):
                    notes.append(f"not restored: {rel} (refused: a link or outside the checkout)")
            except Exception as exc:  # noqa: BLE001 - named in the record
                notes.append(f"not restored: {rel} ({type(exc).__name__}: {exc})")
        self.pre_gate = {}
        return notes

    def _tool_failure(self, session: _Session, what: str, outcome: str = GAVE_UP) -> None:
        notes = self._restore_pre_gate()  # a gate that passed or half-wrote leaves no row behind
        self._reset(session)
        if session.counted:
            self._record_attempt(session, outcome, TOOL, read_checks(session.claim.attempt_dir))
        raise _Stop(TOOL, "; ".join([what, *notes]))

    def _judge(self, session: _Session) -> GateRun | None:
        """The lint, then the gate (D-24). None when the lint failed (the gate never runs)."""
        pick, n = session.claim.pick, session.claim.n
        self.pre_gate = {}
        lint = self.deps.lint(pick)
        if lint == EXIT_TOOL:
            self._tool_failure(session, "the C89 lint could not run (exit 2)")
        if lint != EXIT_OK:
            return None
        claim = session.claim
        self.pre_gate = {rel: _read(self.repo / rel)
                         for rel in (claim.status_rel, FEED, ATTEMPT_LOG.as_posix())}  # fmt: skip
        gate = self.deps.gate(pick, n)
        if gate.exit_code not in (EXIT_OK, EXIT_MISMATCH):
            self._tool_failure(session, f"gate exited {gate.exit_code}")
        stems = sorted(PurePosixPath(name).stem.lower() for name, _ in gate_sha1s(gate.doc))
        if gate.exit_code == EXIT_OK and stems != sorted(EXE_ORDER):  # minor 7
            self._tool_failure(session, f"gate passed but its SHA-1s name {stems}, not both of "
                                        f"{sorted(EXE_ORDER)}")  # fmt: skip
        return gate

    def _salvage(self, session: _Session) -> bool:
        """06-17 review: a LIMIT session keeps its work. When it changed the unit or wrote a
        header, it is judged as usual; a pass is a counted MATCHED. Otherwise it is reset."""
        if session.has_work():
            gate = self._judge(session)
            if gate is not None and gate.exit_code == EXIT_OK:
                self.sessions += 1
                self._commit_match(session, gate, read_checks(session.claim.attempt_dir))
                return True
        self._reset(session)
        return False

    def _counted(self, session: _Session) -> str:
        self.sessions += 1
        claim = session.claim
        summary = read_checks(claim.attempt_dir)
        abort = TIMEOUT if session.result.timed_out else None
        gate = self._judge(session)
        if gate is not None and gate.exit_code == EXIT_OK:
            self._commit_match(session, gate, summary, abort)
            return MATCHED
        if gate is None:
            outcome, abort = PARTIAL, LINT
        else:
            outcome = PARTIAL if (summary.best_percent or 0.0) > 0.0 else GAVE_UP
        self._reset(session)
        if outcome == PARTIAL and summary.best_source is not None:
            if self._partial_gate(session, summary) == EXIT_TOOL:
                self._record_attempt(session, outcome, TOOL, summary)
                raise _Stop(TOOL, "gate --partial exited 2")
        self._record_attempt(session, outcome, abort, summary)
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
        return self.deps.partial_gate(claim.pick, best.relative_to(self.repo).as_posix(), claim.n)

    def _commit_headers(self, session: _Session) -> list[str]:
        """The untracked include/ entries to commit: only the audited new headers. Any other
        untracked entry under include/ stops the night (security ruling)."""
        raw = _git_ok(self.deps.git, ["status", "--porcelain=v1", "--untracked-files=all", "-z",
                                      "--", "include/"])  # fmt: skip
        untracked = [p for p, code in parse_status(raw).items() if code == _UNTRACKED]
        odd = [p for p in untracked if not _HEADER.fullmatch(p)]
        if odd:
            notes = self._restore_pre_gate()
            self._guardrail(session, odd, record=session.counted, extra=notes)
        older = [p for p in untracked if p not in session.new_headers]
        if older:  # fix round 1 minor 5: never silently left out of a match commit
            why = f"untracked headers this session did not write: {_listed(older)}"
            self._tool_failure(session, f"{why} (commit or remove them first)")
        return list(untracked)

    def _commit_match(self, session: _Session, gate: GateRun, summary: CheckSummary,
                      abort: str | None = None) -> None:  # fmt: skip
        claim = session.claim
        headers = self._commit_headers(session)
        paths = [claim.unit_rel, claim.status_rel, FEED, ATTEMPT_LOG.as_posix(), *headers]
        self._record_attempt(session, MATCHED, abort, summary)
        try:
            message = commit_message(exe=claim.pick.exe, function=claim.function,
                                     unit=claim.pick.unit, attempt_n=claim.n,
                                     attempts=self.config.attempts_per_function,
                                     model=session.text("model"), usage=session.usage,
                                     seconds=session.seconds,
                                     sha1s=gate_sha1s(gate.doc))  # fmt: skip
            commit_paths(self.deps.git, message=message,
                         message_file=claim.attempt_dir / COMMIT_MSG, paths=paths)  # fmt: skip
        except Exception as exc:  # fix round 2 J1: any failure, not only a DriverError
            why = f"{type(exc).__name__}: {exc}"
            raise _Stop(TOOL, self._undo_match(session, paths, summary, why)) from exc
        except BaseException as exc:  # minor 3: an interrupt is undone, then re-raised
            undone = self._undo_match(session, paths, summary, type(exc).__name__)
            self.interrupted = f" during the match commit; {undone}"
            raise
        self.matched += 1

    def _undo_match(self, session: _Session, paths: Sequence[str], summary: CheckSummary,
                    why: str) -> str:  # fmt: skip
        """Fix round 1 I2, completed in fix round 2 (J1): a match commit that failed leaves no
        trace of a match. Each step is best-effort with its own note: unstage what it added,
        put status.csv, the feed and the log back to their pre-gate bytes (dropping the
        driver's own uncommitted MATCHED record), reset the attempt. Then the attempt is
        always logged GAVE_UP `tool`, and the returned detail names the original error, every
        step that failed and every path still staged. The caller stops the night."""
        notes = [f"the match commit failed: {why}"]
        try:
            _git_ok(self.deps.git, ["restore", "--staged", "--", *paths])
        except Exception as exc:  # noqa: BLE001 - named below
            notes.append(f"could not unstage: {type(exc).__name__}: {exc}")
        notes += self._restore_pre_gate()
        try:
            self._reset(session)
        except Exception as exc:  # noqa: BLE001 - named below
            notes.append(f"could not reset the attempt: {type(exc).__name__}: {exc}")
        staged = self._staged()
        if staged:
            notes.append(f"still staged: {_listed(staged)}")
        try:
            self._record_attempt(session, GAVE_UP, TOOL, summary)
        except Exception as exc:  # noqa: BLE001 - named below
            notes.append(f"could not record the attempt: {type(exc).__name__}: {exc}")
        if len(notes) > 1:  # fix round 3 K1: an incomplete undo commits nothing tonight
            self.breached = True
        return "; ".join(notes)

    def _staged(self) -> list[str]:
        """Every path staged in the index (best-effort: an unreadable index is named)."""
        try:
            raw = _git_ok(self.deps.git, ["diff", "--cached", "--name-only", "-z"])
        except Exception as exc:  # noqa: BLE001 - the caller names it
            return [f"<unknown: {type(exc).__name__}: {exc}>"]
        return [n for n in raw.decode("utf-8", "surrogateescape").split("\0") if n]

    # --- records ---

    def _base(self, claim: _Claim, kind: str) -> dict:
        return {"kind": kind, "run": claim.run, "exe": claim.pick.exe,
                "function": claim.function, "unit": claim.pick.unit,
                "start": f"0x{claim.pick.start:08X}", "attempt": claim.n}  # fmt: skip

    def _record_attempt(self, session: _Session, outcome: str, abort: str | None,
                        summary: CheckSummary) -> None:  # fmt: skip
        use = session.usage
        record = {**self._base(session.claim, KIND_ATTEMPT), "outcome": outcome,
                  "abort_reason": abort, "turns": use.turns,
                  "tokens": {"input": use.input_tokens, "output": use.output_tokens,
                             "cache_read": use.cache_read_tokens,
                             "cache_creation": use.cache_creation_tokens},
                  "cost_usd": use.cost_usd, "seconds": round(session.seconds, 1),
                  "model": session.text("model"),
                  "cli_version": session.text("claude_code_version"),
                  "check": summary.to_json(), "pack_bytes": session.pack.pack_bytes,
                  "truncated": list(session.pack.truncated), "date": self.deps.today()}  # fmt: skip
        append_record(self.log, record)

    def _record_abort(self, claim: _Claim, retries: int) -> None:
        record = {**self._base(claim, KIND_ABORT), "abort_reason": TRANSIENT, "retries": retries,
                  "date": self.deps.today()}  # fmt: skip
        append_record(self.log, record)

    def _record_run(self, event: str, reason: str, detail: str | None = None, *,
                    checks_failed: Sequence[str] = (),
                    uncommitted: Sequence[str] = ()) -> None:  # fmt: skip
        record = {"kind": KIND_RUN, "run": self.config.run_id, "event": event, "reason": reason,
                  "detail": detail, "sessions": self.sessions, "matched": self.matched,
                  "checks_failed": list(checks_failed), "uncommitted": list(uncommitted),
                  "date": self.deps.today()}  # fmt: skip
        append_record(self.log, record)


def drive(config: DriveConfig, deps: Deps) -> DriveReport:
    """Run one night (see the module docstring)."""
    return _Night(config, deps).run()

# ---- the drive verb (plan 06-25; D-10, D-13, D-24, D-34, D-36, D-48) ----

COMPOSE_RUN = ("docker", "compose", "run", "--rm", "-T", "build")  # -T: output is captured
CONTAINER_CLI = (*COMPOSE_RUN, "uv", "run", "--frozen", "reverseapoc")  # D-24: the gates
COMMAND_TIMEOUT_S = 3600  # a gate re-checks a unit and rebuilds both EXEs; generous, never forever
DRY_RUN_DIR = "dry-run"  # build/driver/<run>/dry-run/<exe>/<func>/context.md


@dataclass(frozen=True)
class DriveOptions:
    """What `reverseapoc drive` was asked to do (D-48 defaults)."""

    repo: Path
    run_id: str
    max_sessions: int = 30
    target_matched: int = 10
    dry_run: bool = False
    canary: bool = False
    json: bool = False

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
    the D-12 unit scaffold."""

    pool: Sequence[Candidate]
    units: Mapping[int, str]
    callees: Mapping[int, tuple[int, ...]]
    pack: Callable[[Pick, Path], PackInfo]
    scaffold: Callable[[Pick], None]


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]


@dataclass(frozen=True)
class Seams:
    """Every effect of the verb: `run` runs every command except git and the session (docker,
    uv, `claude --version`) and returns its exit code and text output; `git` is git_runner;
    `world` loads both EXEs; `session` is session.run_session and `argv` the claude argv
    (session.build_argv with the resolved `claude`). `now` is the wall clock the console
    stamps read (local time; Deps.clock stays the monotonic clock for durations)."""

    run: Runner
    git: Callable[[Sequence[str]], subprocess.CompletedProcess]
    world: Callable[[], Mapping[str, ExeWorld]]
    session: Callable[..., SessionResult]
    argv: Callable[[str], Sequence[str]]
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


def finish(run: Runner, *, run_dir: Path) -> list[str]:
    """D-24: the end-of-run checks, in the container and in this order: a from-clean ninja
    verify (configure, clean, verify), then `gate --all`. Both always run; each one's output is
    written by the driver to build/driver/<run>/end-*.log. Returns one string per failed check
    (`ninja verify exit 1`), which the driver pins in the ENDED record before the chore commit
    (06-23 fix round 4 L1: wired as Deps.end_of_run)."""
    failed = []
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, log, argv in END_OF_RUN:
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


def real_deps(options: DriveOptions, seams: Seams, worlds: Mapping[str, ExeWorld], *,
              today: str | None = None) -> Deps:  # fmt: skip
    """The Deps a real night uses: the picker over both pools minus status.csv's matched and
    this pass's partial rows (AGT-07), picker.requeue with the matched set read now, the
    worlds' scaffold and pack, the claude argv and session, and the container lint and gates
    (D-24). `today` (UTC) names this pass."""
    day = today or _today()
    config_root = options.config_root
    excluded = excluded_keys(config_root, day)

    def queue(difficult: Container[Key]) -> Iterable[Pick]:
        return picker_queue(_pools(worlds), units=_units(worlds), excluded=excluded,
                            difficult=difficult)  # fmt: skip

    def requeue(difficult: Mapping[Key, tuple[Key, ...]]) -> Iterable[Key]:
        keys = frozenset(difficult)
        empty = next(iter(queue(keys)), None) is None
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
                scaffold=lambda pick: worlds[pick.exe].scaffold(pick),
                pack=lambda pick, directory: worlds[pick.exe].pack(pick, directory),
                argv=seams.argv, session=seams.session, lint=lint,
                gate=lambda pick, n: _container_gate(seams.run, gate_argv(pick, n)),
                partial_gate=lambda pick, src, n: seams.run(
                    partial_gate_argv(pick, src, n)).returncode,
                remove_containers=container_remover(options.repo, seams.run),
                git=seams.git, today=lambda: day,
                end_of_run=lambda: finish(seams.run, run_dir=options.run_dir))  # fmt: skip


def _emit(options: DriveOptions, doc: Mapping, text: Sequence[str]) -> None:
    """F13: in --json mode stdout carries exactly this one JSON document; else the text."""
    if options.json:
        print(json.dumps(doc, separators=(",", ":")))
    else:
        for line in text:
            print(line)


def _pick_doc(options: DriveOptions, pick: Pick, pack: Path, info: PackInfo) -> dict:
    return {"exe": pick.exe, "start": f"0x{pick.start:08X}", "name": pick.name,
            "unit": pick.unit, "size": pick.size, "score": pick.score,
            "pack": pack.relative_to(options.repo).as_posix(),
            "pack_bytes": info.pack_bytes}  # fmt: skip


def pilot_picks(options: DriveOptions, worlds: Mapping[str, ExeWorld], *, today: str) -> list[Pick]:
    """D-10: the pilot's 10 picks (5 + 5, interleaved, variety rule), skipping status.csv's
    matched and this pass's partial rows and the difficult list."""
    difficult = load_difficult(Path(options.repo) / DIFFICULT)
    return picker_pilot(_pools(worlds), units=_units(worlds),
                        excluded=excluded_keys(options.config_root, today),
                        difficult=frozenset(difficult))  # fmt: skip


def night_top_picks(options: DriveOptions, worlds: Mapping[str, ExeWorld], *,
                    today: str) -> list[Pick]:  # fmt: skip
    """The queue's first `max_sessions` picks: no night attempts more functions than that, so
    their Ghidra drafts are the ones worth precomputing (D-13)."""
    difficult = frozenset(load_difficult(Path(options.repo) / DIFFICULT))
    stream = picker_queue(_pools(worlds), units=_units(worlds),
                          excluded=excluded_keys(options.config_root, today),
                          difficult=difficult)  # fmt: skip
    return [pick for _, pick in zip(range(options.max_sessions), stream, strict=False)]


def dry_run(options: DriveOptions, worlds: Mapping[str, ExeWorld], picks: Sequence[Pick]) -> int:
    """The pilot picks with their packs built under build/driver/<run>/dry-run/; no claude, no
    gate (D-10)."""
    docs, lines = [], []
    for pick in picks:
        directory = options.run_dir / DRY_RUN_DIR / pick.exe / f"func_{pick.start:08X}"
        info = worlds[pick.exe].pack(pick, directory)
        doc = _pick_doc(options, pick, directory / PACK_FILE, info)
        docs.append(doc)
        lines.append(f"{pick.exe} {doc['start']} {pick.name} {pick.unit} size {pick.size} "
                     f"score {pick.score} pack {doc['pack']} ({info.pack_bytes} bytes)")
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


def _refusal(options: DriveOptions, refused: Refused) -> int:
    doc = {"event": REFUSED, "reason": refused.reason, "detail": refused.detail}
    if options.json:
        _emit(options, doc, [])
    else:
        print(f"reverseapoc drive: refused ({refused.reason}): {refused.detail}", file=sys.stderr)
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
    """`reverseapoc drive`: the preflight, then the canary, the dry run or one night."""
    if not _RUN_ID.fullmatch(options.run_id):
        return _refusal(options, Refused("run id", f"{options.run_id!r} is not [A-Za-z0-9_.-]+"))
    log = _Log(options, seams)
    try:
        with _phase("preflight"):
            preflight(options, seams, check_cli=not options.dry_run, log=log)
        if options.canary:
            with _phase("canary"):
                return run_canary(options, seams)
        worlds = _load_worlds(seams)
        today = _today()
        with _phase("picks"):
            picks = (pilot_picks if options.dry_run else night_top_picks)(options, worlds,
                                                                           today=today)
        with _phase("drafts"):
            _drafts(log, picks)
        if options.dry_run:
            with _phase("pack"):
                return dry_run(options, worlds, picks)
        with _phase("picks"):
            deps = real_deps(options, seams, worlds, today=today)
    except Refused as refused:
        return _refusal(options, refused)
    config = DriveConfig(run_id=options.run_id, repo_root=options.repo,
                         tested_major=TESTED_MAJOR, min_cli_version=MIN_CLI_VERSION,
                         max_sessions=options.max_sessions,
                         target_matched=options.target_matched,
                         base_env=seams.base_env)  # fmt: skip
    report = drive(config, deps)
    doc = {"event": report.event, "reason": report.reason, "sessions": report.sessions,
           "matched": report.matched, "detail": report.detail,
           "checks_failed": list(report.checks_failed), "exit_code": report.exit_code}  # fmt: skip
    _emit(options, doc, [f"{report.event} {report.reason}: {report.sessions} sessions, "
                         f"{report.matched} matched" + (f" ({report.detail})" if report.detail
                                                        else "")])  # fmt: skip
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
    f"5. Run the Bash command `{CANARY_CHECK}` with the Bash tool's timeout set to 600000. "
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
                   checks: _Checks) -> None:  # fmt: skip
    repo = Path(options.repo)
    init = streamjson.init_event(events)
    problems = streamjson.check_init(init, tested_major=TESTED_MAJOR,
                                     min_version=MIN_CLI_VERSION)  # fmt: skip
    checks.add(not problems, "init: " + ("; ".join(problems) if problems else
                                         f"claude {(init or {}).get('claude_code_version')}, "
                                         "model, tools, no MCP server, no plugin"))  # fmt: skip
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


def _tree_checks(probe: _Night, before: _Snapshot, checks: _Checks) -> None:
    """git status clean, and nothing the night's audit pins or fingerprints changed."""
    raw = _git_ok(probe.deps.git, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
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
    head = _git_ok(probe.deps.git, ["rev-parse", "HEAD"]).decode("utf-8").strip()
    raw = _git_ok(probe.deps.git, ["for-each-ref", "--format=%(refname) %(objectname)"])
    refs = dict(line.split(" ", 1) for line in raw.decode("utf-8", "replace").splitlines()
                if " " in line)  # fmt: skip
    return {"HEAD": head, **refs}


def _after_session(options: DriveOptions, seams: Seams, events: Sequence[dict],
                   attempt_dir: Path, checks: _Checks) -> None:  # fmt: skip
    """The stream checks; an error in them is a FAIL line after the lines so far (fix round
    2: the session ran, so the canary reports, it never refuses)."""
    try:
        _canary_checks(options, events, attempt_dir, checks)
    except Exception as exc:  # noqa: BLE001 - reported, never a PASS
        checks.add(False, f"checking the stream failed: {type(exc).__name__}: {exc}")


def run_canary(options: DriveOptions, seams: Seams) -> int:
    """One real session (owner only) with CANARY_PROMPT under the matching settings, claiming
    ufo2p/u_000a34f0 func_000A3980 with absolute paths under build/driver/canary/ (F12). PASS
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
    attempt_dir.mkdir(parents=True)
    pick = Pick(CANARY_EXE, int(CANARY_FUNC[len("func_"):], 16), CANARY_FUNC, CANARY_UNIT, 0, 0)
    claim = _Claim(pick, options.run_id, repo, 1)
    base = seams.base_env if seams.base_env is not None else os.environ
    env = {**claim.env(base), attempt.DIR_ENV: str(attempt_dir),
           attempt.NOTES_ENV: str(attempt_dir / attempt.NOTES_FILE)}  # fmt: skip
    probe = _probe(options, seams)
    before = probe._snapshot()
    refs_before = _refs(probe)
    checks = _Checks()
    try:
        result = seams.session(seams.argv(CANARY_PROMPT), cwd=repo, env=env,
                               transcript=attempt_dir / TRANSCRIPT,
                               timeout_s=CANARY_TIMEOUT_S)  # fmt: skip
    except Exception as exc:  # a crash is a FAIL with the tree still measured
        checks.add(False, f"the session raised {type(exc).__name__}: {exc}")
    else:
        _after_session(options, seams, result.events, attempt_dir, checks)
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
           "checks": [{"ok": ok, "check": text} for ok, text in checks.lines]}  # fmt: skip
    lines = [f"{'PASS' if ok else 'FAIL'}: {text}" for ok, text in checks.lines]
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

    def pack(pick: Pick, directory: Path) -> PackInfo:
        built = attempt.make_pack(data, rows[pick.start], src=roots.src, config=roots.config,
                                  asm_root=roots.asm, roots=roots, calls=calls)  # fmt: skip
        write_pack(built, directory, root=roots.repo)
        return PackInfo(built.pack_bytes, tuple(built.truncated))

    def scaffold(pick: Pick) -> None:
        unit = next((u for u in data.units if u.unit == pick.unit), None)
        if unit is None:
            raise DriverError(f"{pick.exe}: no unit {pick.unit} in units.csv")
        path = Path(roots.src) / exe / f"{pick.unit}.c"
        write_unit_source(path, scaffold_unit(data.target.name, unit, list(data.rows)))

    return ExeWorld(pool=candidates(assessments, data.symbols),
                    units={row.start: row.unit for row in data.rows},
                    callees=dict(calls.callees), pack=pack, scaffold=scaffold)  # fmt: skip


def default_seams(repo: Path) -> Seams:
    """The real effects: commands in the checkout, git_runner, both EXEs through check's loader
    (attempt.ROOTS), session.run_session with D-06's argv for the `claude` on PATH."""
    claude = shutil.which("claude") or "claude"
    return Seams(run=command_runner(repo), git=git_runner(repo),
                 world=lambda: {exe: load_world(exe, roots=attempt.ROOTS) for exe in EXE_ORDER},
                 session=run_session, argv=lambda prompt: build_argv(prompt, claude=claude),
                 claude=claude)  # fmt: skip

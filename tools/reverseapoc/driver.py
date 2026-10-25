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
   size, mtime_ns) of the venv's site-packages and of every repo __pycache__ must not change
   (security rulings). A stray path stops the night (STOPPED `guardrail`) with nothing
   committed: each stray file is copied or moved into build/driver/<run>/quarantine/ (created
   at run start; no link followed, O_EXCL, never overwritten) and put back as it was, the
   attempt is reset, the snapshot is taken again, and the record lists every path. A session
   that raises is contained the same way before its ERROR stop. build/ itself is not audited:
   the attempt wrapper writes there by design (a known limit);
3. streamjson.classify (D-08): STOP stops the night; a check_init problem stops it too; LIMIT
   keeps the session's work (the gate runs on it as usual), then backs off 60, 120, 240 s and
   polls every 300 s, not counted; TRANSIENT resets and relaunches, and after 3 such sessions
   writes an `abort` record, not counted; ATTEMPT_DONE (a result or a wall-clock timeout) is
   counted;
4. a counted session: the C89 lint of the unit, then the container gate. Only gate exit 0 is a
   match (D-24): never the transcript, the result event or /goal's verdict. A match is one
   commit with explicit paths only (D-25). Otherwise the attempt is reset (D-34) and logged
   PARTIAL (best plain check above 0%, its C saved under best/ and `gate --partial` run) or
   GAVE_UP; a failed lint is PARTIAL "lint".

Every effect is an injected dependency (`Deps`), so the tests run the stand-in claude
(tests/fakeclaude.py), fake gates and a tmp git repo. The `drive` verb that wires the real ones
follows in plan 06-25. Every git call goes through `--literal-pathspecs`, so no path is a glob.

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
import time
from collections.abc import Callable, Container, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import attempt, hooks, streamjson
from .fileio import write_atomic
from .picker import EXE_ORDER, Key, Pick
from .session import TIMEOUT_S, SessionResult, goal_prompt
from .streamjson import Disposition

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
TRANSIENT_TRIES = 3  # D-08: overloaded/server_error/no result, then the attempt is aborted
EXIT_OK, EXIT_MISMATCH, EXIT_TOOL = 0, 1, 2

MATCHED, PARTIAL, GAVE_UP = "MATCHED", "PARTIAL", "GAVE_UP"
KIND_ATTEMPT, KIND_ABORT, KIND_RUN = "attempt", "abort", "run"
STARTED, STOPPED, ENDED = "STARTED", "STOPPED", "ENDED"
START = "start"
NOTHING_TO_DO, MAX_SESSIONS, TARGET_MATCHED, QUEUE_EXHAUSTED = (
    "nothing to do", "max sessions", "target matched", "queue exhausted")  # fmt: skip
GUARDRAIL, STOP_SIGNAL, INIT, ERROR, TOOL = "guardrail", "stop signal", "init", "error", "tool"
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


@dataclass(frozen=True)
class DriveReport:
    """How the night ended: ENDED or STOPPED, why, and its counts."""

    event: str
    reason: str
    sessions: int
    matched: int
    detail: str | None = None

    @property
    def exit_code(self) -> int:
        return 0 if self.event == ENDED else 1


def git_runner(repo: Path, *, env: Mapping[str, str] | None = None):
    """`git <args>` in `repo` as an argv list, never a shell; stdout and stderr as bytes."""

    def git(args: Sequence[str]) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=repo, env=None if env is None else dict(env),
                              capture_output=True, check=False)  # fmt: skip

    return git


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
        "date": _CLAIM_FIELDS["date"],
    },
}
RUN_REASONS = {
    STARTED: (START,),
    STOPPED: (GUARDRAIL, STOP_SIGNAL, INIT, ERROR, TOOL),
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


def _walk(root: Path, *, skip_top: Sequence[str] = ()) -> Iterable[tuple[Path, list[str]]]:
    """(directory, its file names) under `root`, never following a link, the top-level
    directories in `skip_top` left out."""
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        if Path(dirpath) == root:
            dirnames[:] = [d for d in dirnames if d not in skip_top]
        yield Path(dirpath), filenames


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
                attempt.NOTES_ENV: str(self.notes)}  # fmt: skip


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
    refused: list[str] = field(default_factory=list)


class _Stop(Exception):
    """Ends the night with a STOPPED record. `guardrail` stops commit nothing."""

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

    # --- the night ---

    def run(self) -> DriveReport:
        self._record_run(STARTED, START)
        try:
            event, reason, detail = ENDED, self._loop(), None
        except _Stop as stop:
            event, reason, detail = STOPPED, stop.reason, stop.detail
        self._record_run(event, reason, detail)
        if not (event == STOPPED and reason == GUARDRAIL):  # after a breach: commit nothing
            self._commit_log(stopped=event == STOPPED)
        return DriveReport(event, reason, self.sessions, self.matched, detail)

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
            if self.live is not None:
                try:
                    self._reset(self.live)
                except Exception:  # noqa: BLE001 - the stop below names the first failure
                    pass
            raise _Stop(ERROR, f"{type(exc).__name__}: {exc}") from exc
        finally:
            self.live = None

    def _attempt(self, pick: Pick, n: int) -> str | None:
        """Launch until one session counts (its outcome), a LIMIT session matches (MATCHED), or
        TRANSIENT_TRIES sessions in a row were transient (None, an abort record)."""
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
                if transient >= TRANSIENT_TRIES:
                    self._record_abort(claim, transient)
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
        """Security ruling (third pass): (size, mtime_ns) of every file in the venv's
        site-packages and in every __pycache__ of the checkout outside build/, .venv and .git;
        no contents are read."""
        roots = [d for pattern in _SITE_GLOBS for d in self.repo.glob(pattern) if d.is_dir()]
        found: dict[str, tuple[int, int]] = {}
        for root in roots:
            for directory, names in _walk(root):
                self._print_files(found, directory, names)
        for directory, names in _walk(self.repo, skip_top=_NOT_FINGERPRINTED):
            if directory.name == _PYCACHE:
                self._print_files(found, directory, names)
        return found

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
        except Exception as exc:
            # Third pass: contain what the session left before the ERROR stop.
            session = self._measure(claim, None, pack, 0.0, before, scaffolded, unit_before)
            stray = self._strays(session)
            contained = f"; {self._contain_and_reset(session, stray)}" if stray else ""
            if not stray:
                self._reset(session)
            why = f"the session raised {type(exc).__name__}: {exc}{contained}"
            raise _Stop(ERROR, why) from exc
        finally:
            self.deps.remove_containers(attempt.container_prefix(claim.attempt_dir))
        seconds = self.deps.clock() - start
        session = self._measure(claim, result, pack, seconds, before, scaffolded, unit_before)
        self.live = session
        self._audit(session)
        if session.disposition is Disposition.STOP:
            self._reset(session)
            raise _Stop(STOP_SIGNAL, "the session's stream carries a D-08 STOP signal")
        self._check_init(session)
        return session

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

    def _guardrail(self, session: _Session, stray: Sequence[str], *, record: bool) -> None:
        """Security ruling: a breach never leaves the strays in place and never deletes one.
        Each stray file is copied (tracked, or pinned with earlier bytes) or moved (new) into
        build/driver/<run>/quarantine/<path>, then put back as it was before the session; the
        attempt is reset as usual and the STOPPED record lists every path."""
        detail = self._contain_and_reset(session, stray)
        if record:
            self._record_attempt(session, GAVE_UP, GUARDRAIL,
                                 read_checks(session.claim.attempt_dir))  # fmt: skip
        raise _Stop(GUARDRAIL, detail)

    def _contain_and_reset(self, session: _Session, stray: Sequence[str]) -> str:
        """Contain the strays, reset the attempt, take the pinned snapshot and the fingerprint
        again, and describe all of it. A refused quarantine write (a link) writes nothing more
        and is named."""
        files = [s for s in stray if not s.endswith(_TRANSCRIPT_MARK)]
        done = self._contain(session, files)
        self._reset(session)
        detail = (f"stray paths: {_listed(list(stray))}; restored: {_listed(done.restored)}"
                  f"; quarantined: {_listed(done.quarantined)}")  # fmt: skip
        if done.not_contained:
            detail += f"; not contained: {_listed(done.not_contained)}"
        if done.refused:
            detail += "; " + "; ".join(done.refused)
        still = self._still_changed(session)
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
        tracked = self._tracked()
        before = session.before
        done = _Contained()
        for name in files:
            pinned = name in session.pinned_changed and name.casefold() not in tracked
            path = self._pinned_path(name) if pinned else self.repo / name
            earlier = before.pinned.get(name) if pinned else before.data.get(name)
            # A fingerprinted file has no saved bytes: a new one moves out, a changed one is
            # copied and stays (named again under "still changed").
            changed_print = name in session.print_changed and name in before.prints
            move = earlier is None and name.casefold() not in tracked and not changed_print
            if path.is_file() or _is_link(path):
                if not self._keep(done, name, path, move=move) and move:
                    done.not_contained.append(name)
                    continue
            restored = done.restored
            if not pinned and name.casefold() in tracked and earlier is None:
                _git_ok(self.deps.git, ["restore", "--source=HEAD", "--staged", "--worktree",
                                        "--", name])  # fmt: skip
                restored.append(name)
            elif earlier is not None:
                write_atomic(path, earlier)
                if name.casefold() in tracked:
                    _git_ok(self.deps.git, ["restore", "--staged", "--", name])
                restored.append(name)
        for name in (session.claim.unit_rel, *session.new_headers):
            if name in session.changed and (self.repo / name).is_file():
                self._keep(done, name, self.repo / name, move=False)
        return done

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

    def _tool_failure(self, session: _Session, what: str, outcome: str = GAVE_UP) -> None:
        self._reset(session)
        if session.counted:
            self._record_attempt(session, outcome, TOOL, read_checks(session.claim.attempt_dir))
        raise _Stop(TOOL, what)

    def _judge(self, session: _Session) -> GateRun | None:
        """The lint, then the gate (D-24). None when the lint failed (the gate never runs)."""
        pick, n = session.claim.pick, session.claim.n
        lint = self.deps.lint(pick)
        if lint == EXIT_TOOL:
            self._tool_failure(session, "the C89 lint could not run (exit 2)")
        if lint != EXIT_OK:
            return None
        gate = self.deps.gate(pick, n)
        if gate.exit_code not in (EXIT_OK, EXIT_MISMATCH):
            self._tool_failure(session, f"gate exited {gate.exit_code}")
        if gate.exit_code == EXIT_OK and len(gate_sha1s(gate.doc)) != 2:
            self._tool_failure(session, "gate passed but its output does not name both SHA-1s")
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
            self._guardrail(session, odd, record=session.counted)
        return [p for p in untracked if p in session.new_headers]

    def _commit_match(self, session: _Session, gate: GateRun, summary: CheckSummary,
                      abort: str | None = None) -> None:  # fmt: skip
        claim = session.claim
        headers = self._commit_headers(session)
        self._record_attempt(session, MATCHED, abort, summary)
        usage = session.usage
        message = commit_message(exe=claim.pick.exe, function=claim.function,
                                 unit=claim.pick.unit, attempt_n=claim.n,
                                 attempts=self.config.attempts_per_function,
                                 model=session.text("model"), usage=usage,
                                 seconds=session.seconds, sha1s=gate_sha1s(gate.doc))  # fmt: skip
        paths = [claim.unit_rel, claim.status_rel, FEED, ATTEMPT_LOG.as_posix(), *headers]
        commit_paths(self.deps.git, message=message, message_file=claim.attempt_dir / COMMIT_MSG,
                     paths=paths)  # fmt: skip
        self.matched += 1

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

    def _record_run(self, event: str, reason: str, detail: str | None = None) -> None:
        record = {"kind": KIND_RUN, "run": self.config.run_id, "event": event, "reason": reason,
                  "detail": detail, "sessions": self.sessions, "matched": self.matched,
                  "date": self.deps.today()}  # fmt: skip
        append_record(self.log, record)


def drive(config: DriveConfig, deps: Deps) -> DriveReport:
    """Run one night (see the module docstring)."""
    return _Night(config, deps).run()

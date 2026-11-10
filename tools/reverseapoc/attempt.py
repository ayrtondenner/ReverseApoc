# SPDX-License-Identifier: GPL-3.0-or-later
"""The attempt wrapper (D-44): the only commands a matching session runs through Bash.

`uv run --frozen reverseapoc attempt check|asm|context|giveup|plan` is bound to the claimed
function.
The claim comes only from the driver's environment (REVERSEAPOC_CLAIM, REVERSEAPOC_FUNC,
REVERSEAPOC_ATTEMPT_DIR), each validated here; no agent argument chooses the unit, the
function, the flags, the Watcom tree or the source root. The accepted argument shapes are
exactly hooks.forms_for(kind) (ruling F27), which the matching-session hook allows:
hooks.MATCHING_FORMS in a matching session, the five hooks.ATTEMPT_FORMS in a readability one.

`attempt giveup` (07.2-02, 999.5, D-04, D-26) validates the session's giveup.json, the sibling
of notes.md, with `read_giveup`, the validator the driver reuses when it records the give-up;
it reserves no check slot and runs no container.

A matching session's `attempt check` (07.2-03, 999.6, D-01..D-03, D-26) first needs the
session's plan.json (`read_plan`: FRAME, SLOT, CALL and REGION entries, the regions covering the
claimed row) and a check-note.json (`read_check_note`: change, why and expect), both siblings of
notes.md; `attempt plan` validates the plan alone, with no slot and no container. They are
validated after the budget test and before the slot is reserved, so a
refusal (exit 2) uses none of the checks. After the run the note moves to checks/NNNN.note.json
with what the run observed, written by the tool (D-02); checks.jsonl points at it. A readability
check needs neither.

`attempt check` runs `reverseapoc check <claim> --json` in the container through an injectable
runner, at most CHECK_BUDGET times per attempt (D-07). One run at a time: each holds
`check.lock` and reserves its number by creating the snapshot of the C it checks
(`checks/NNNN.c`, ruling F10, O_EXCL), so a reserved slot counts even if the run then fails.
Each run keeps the JSON (`checks/NNNN.json`) and appends one line to `checks.jsonl`, all under
the gitignored attempt directory in build/driver/. Under a function whose bytes differ the
summary prints check's window (`functions[].window`: addresses, mnemonics and operands of ours
beside the original's around the first difference, never bytes); it reaches the terminal and
checks/NNNN.json only, never checks.jsonl. `--sweep` runs the
D-17 flag matrix as a diagnostic: a cell at 100% under flags other than the unit's cflags.txt
rule is logged as `sweep_hit`, for the owner to decide (D-18 of Phase 5; cflags.txt is
owner-only).

In a readability session (REVERSEAPOC_SESSION_KIND=readability, 07-31; D-17, D-18, D-20) a
plain `attempt check` also runs readlint on the host over the view unit, after the container
check, and its verdict is OK only when both pass: every defined function still at objdiff 100%
with relocations and bytes ok and every splice identical, and readlint clean. The agent's
command surface does not change (hooks.ATTEMPT_FORMS); the driver checks both again at landing.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import asm, check, contextpack, ghidra, lift, unitdefs
from .cflags import DEFAULT_CFLAGS, load_cflags, select_rule
from .check import DEFAULT_CONFIG, DEFAULT_SRC, EXIT_MISMATCH, EXIT_OK, EXIT_TOOL, PERFECT
from .fileio import write_atomic
from .functions import (
    KIND_DATA_IN_CODE,
    KIND_GAME,
    KIND_THUNK,
    FunctionRow,
    read_functions_csv,
    read_symbols_csv,
)
from .hooks import (
    ATTEMPT_PREFIX,
    CHECK_NOTE_NAME,
    CLAIM_ENV,
    GIVEUP_NAME,
    NOTES_ENV,
    PLAN_NAME,
    PROPOSALS_ENV,
    SESSION_KIND_ENV,
    SESSION_KINDS,
    UNIT_FILE_ENV,
    attempt_form_matches,
    forms_for,
)
from .proposals import Rename, read_proposals, rename_problem
from .readlint import ReadlintResult, Violation, run_readlint, unmarked_declarations
from .status import read_status, status_path
from .targets import DEFAULT_MANIFEST, DEFAULT_ORIG, REPO_ROOT, load_manifest
from .unitdefs import DATA_KIND, FUNC_KIND

FUNC_ENV = "REVERSEAPOC_FUNC"
DIR_ENV = "REVERSEAPOC_ATTEMPT_DIR"
CHECK_BUDGET = 25  # D-07: "or stop after 25 check runs", enforced here
CHECK_TIMEOUT = 580  # seconds; under the Bash tool's 600 s cap, so the run is still logged
RM_TIMEOUT = 15  # seconds for `docker rm -f` after a timeout: 580 + 15 < 600 (fix round 2 N2)
CHECKS_DIR = "checks"
CHECK_LOG = "checks.jsonl"
CHECK_LOCK = "check.lock"
NOTES_FILE = "notes.md"  # REVERSEAPOC_ATTEMPT_NOTES must be <attempt dir>/notes.md (06-23, M8)
# D-24 P7: the session's private view of HEAD, <attempt dir>/view/ with src/, include/, config/
# (cflags.txt and the per-EXE CSVs) and build/; checks are rooted in it when the driver sets
# REVERSEAPOC_UNIT_FILE, so concurrent sessions never see each other's edits.
VIEW_DIR = "view"
VIEW_SRC = "src"
VIEW_CONFIG = "config"
VIEW_BUILD = "build"
VIEW_CFLAGS = Path(VIEW_CONFIG) / "cflags.txt"
VIEW_LOG = Path(VIEW_BUILD) / "logs" / "cc.log"
PROPOSALS_FILE = "proposals.jsonl"  # REVERSEAPOC_PROPOSALS must be <attempt dir>/proposals.jsonl
UNIT_BASE = "unit-base.c"  # 07.2-07: <attempt dir>/unit-base.c, the view unit at launch (driver's)
# 261109-gzw: <attempt dir>/view/build/attempt-cache/ keeps attempt asm/context output. It sits in
# the view's build/ (VIEW_BUILD), which the driver's audit invariant (b) skips.
CACHE_DIR = "attempt-cache"
CACHE_FORMAT = 1
_SNAPSHOT = re.compile(r"([0-9]{4})\.c")  # checks/NNNN.c: one reserved run
_O_BINARY = getattr(os, "O_BINARY", 0)  # Windows: no newline translation in the snapshot
DRIVER_PARTS = ("build", "driver")
CONTAINER_RUN = ("docker", "compose", "run", "--rm", "-T")
CONTAINER_CHECK = ("build", "uv", "run", "--frozen", "reverseapoc", "check")
CONTAINER_PREFIX = "reverseapoc-attempt-"  # + 8 hex of the attempt dir + -NNNN (M7, 06-23)
_DIR_HEX = 8
_CLAIM = re.compile(r"(ufo2p|tacp)/([a-z0-9_]+)")
_FUNC = re.compile(r"func_([0-9A-F]{8})")
_HEX = 16
_TAIL_LINES = 40  # of a failed run's output shown to the agent
MEASURED = "measured"  # a sweep cell's status once compiled and diffed
READABILITY = SESSION_KINDS[1]  # the session kind whose check adds readlint (07-31)
FUNCTIONS_CSV = "functions.csv"  # config/<exe>/ tables a check and a rename proposal read
SYMBOLS_CSV = "symbols.csv"
UNITS_CSV = "units.csv"  # read by check.load_exe; the asm/context cache digests it
# 07.2-02 (999.5): the give-up record a matching session leaves in giveup.json. D-04's survey
# categories (narrowed by D-26: no `difficult.json` category), in RULINGS order; the driver's
# GIVEUP_CATEGORIES is this object (the wrapper cannot import the driver).
GIVEUP_CATEGORIES = ("flags", "block_layout", "stack_layout", "register_allocation",
                     "instruction_idiom", "types_or_struct", "call_convention", "compile_error",
                     "other")  # fmt: skip
GIVEUP_TEXTS = ("tried", "still_differs", "suspected_cause")
GIVEUP_KEYS = ("category", *GIVEUP_TEXTS)
GIVEUP_TEXT_CAP = 200  # the driver's _TEXT_CAP, so a validated text fits the record unchanged
_C_CHARS = "{};"  # no C text in a give-up (D-04, D-23): a brace or a semicolon is refused
_LONG_HEX = re.compile(r"[0-9A-Fa-f]{65,}")  # the driver's record-wide rule (D-23)


class AttemptError(ValueError):
    """The wrapper refuses: a bad environment, an argument outside ATTEMPT_FORMS, the check
    budget used, an unreadable unit file. The CLI turns it into exit 2."""


@dataclass(frozen=True)
class Roots:
    """Where the wrapper reads and writes; the defaults are the repository's own trees."""

    repo: Path = REPO_ROOT
    orig: Path = DEFAULT_ORIG
    manifest: Path = DEFAULT_MANIFEST
    config: Path = DEFAULT_CONFIG
    src: Path = DEFAULT_SRC
    asm: Path = REPO_ROOT / "asm"
    cflags: Path = DEFAULT_CFLAGS
    common_h: Path = REPO_ROOT / "include" / "common.h"
    matching: Path = REPO_ROOT / "docs" / "matching.md"

    @property
    def driver(self) -> Path:
        return Path(self.repo).resolve().joinpath(*DRIVER_PARTS)


ROOTS = Roots()  # read at call time; tests replace it


@dataclass(frozen=True)
class Ran:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False  # the runner stopped the client; the container may still run (M7)


Runner = Callable[..., Ran]  # runner(argv) for a check; runner(argv, timeout=s) for a removal


def default_runner(argv: Sequence[str], *, timeout: float = CHECK_TIMEOUT) -> Ran:
    """Runs argv from the repository root (where compose.yaml is), no shell, for at most
    `timeout` seconds. A missing docker or a timeout becomes a failed run (exit 2), so it is
    still logged and counted."""
    try:
        proc = subprocess.run(list(argv), cwd=ROOTS.repo, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              check=False)  # fmt: skip
    except FileNotFoundError as exc:
        return Ran(EXIT_TOOL, "", f"{argv[0]} not found: {exc}")
    except subprocess.TimeoutExpired:
        command = " ".join(argv[:3])
        return Ran(EXIT_TOOL, "", f"`{command}` ran longer than {timeout:g} s and was stopped",
                   timed_out=True)  # fmt: skip
    return Ran(proc.returncode, proc.stdout or "", proc.stderr or "")


RUNNER: Runner = default_runner  # read at call time; tests replace it
CLOCK: Callable[[], float] = time.monotonic  # times each run (M2); tests replace it


def form_allowed(argv: Sequence[str], kind: str = SESSION_KINDS[0]) -> bool:
    """Whether `argv` (after `attempt`) is one of hooks.forms_for(kind) (ruling F27, D-26: a
    readability session gets no matching-only form)."""
    return attempt_form_matches(argv, forms_for(kind))


def forms_text(kind: str = SESSION_KINDS[0]) -> str:
    return "; ".join(" ".join((*ATTEMPT_PREFIX, *form)) for form in forms_for(kind))


# ---- the claim (D-44: from the driver's environment only) ----


def _inside(path: Path, anchor: Path) -> bool:
    """`path` strictly below `anchor`, compared part by part with exact case (contextpack's
    rule: the container's file system does not fold case, and .gitignore's build/ does not
    cover Build/)."""
    parts, base = path.parts, anchor.parts
    return len(parts) > len(base) and tuple(parts[: len(base)]) == tuple(base)


@dataclass(frozen=True)
class Claim:
    exe: str  # ufo2p or tacp
    unit: str
    function: str  # func_XXXXXXXX
    attempt_dir: Path  # resolved, below build/driver/
    notes: Path  # REVERSEAPOC_ATTEMPT_NOTES as the driver set it: <attempt dir>/notes.md
    # D-24 (07-11): REVERSEAPOC_UNIT_FILE, resolved: <attempt dir>/view/src/<exe>/<unit>.c; None
    # is a legacy (Phase 6) session, whose checks read the shared src/.
    unit_file: Path | None = None
    proposals: Path | None = None  # REVERSEAPOC_PROPOSALS: <attempt dir>/proposals.jsonl
    kind: str = SESSION_KINDS[0]  # REVERSEAPOC_SESSION_KIND; absent means matching

    @property
    def view_root(self) -> Path:
        return self.attempt_dir / VIEW_DIR

    @property
    def target(self) -> str:
        return f"{self.exe}/{self.unit}"

    @property
    def address(self) -> int:
        return int(self.function[len("func_") :], _HEX)

    @classmethod
    def from_env(cls, env: Mapping[str, str], *, roots: Roots) -> Claim:
        claim = _CLAIM.fullmatch(env.get(CLAIM_ENV) or "")
        if claim is None:
            raise AttemptError(f"{CLAIM_ENV} must be set by the driver to ufo2p/<unit> or "
                               "tacp/<unit> (unit [a-z0-9_]+)")  # fmt: skip
        function = env.get(FUNC_ENV) or ""
        if _FUNC.fullmatch(function) is None:
            raise AttemptError(f"{FUNC_ENV} must be set by the driver to func_XXXXXXXX "
                               "(8 upper-case hex digits)")  # fmt: skip
        exe, unit = claim.group(1), claim.group(2)
        attempt_dir = _attempt_dir(env, roots)
        unit_file = _unit_file(env, roots, attempt_dir, exe, unit)
        view = unit_file is not None
        return cls(exe, unit, function, attempt_dir, _notes(env, roots, attempt_dir), unit_file,
                   _proposals(env, roots, attempt_dir, view=view),
                   _kind(env, view=view))  # fmt: skip


def _attempt_dir(env: Mapping[str, str], roots: Roots) -> Path:
    value = env.get(DIR_ENV) or ""
    anchor = roots.driver
    if not value:
        raise AttemptError(f"{DIR_ENV} must be set by the driver to a directory below {anchor}")
    path = (Path(roots.repo) / value).resolve()  # an absolute value replaces the root
    if not _inside(path, anchor) or not path.is_dir():
        raise AttemptError(f"{DIR_ENV} {value!r} is not an existing directory below {anchor} "
                           "(the gitignored build/driver/, exact case)")  # fmt: skip
    return path


def _notes(env: Mapping[str, str], roots: Roots, attempt_dir: Path) -> Path:
    """M8: REVERSEAPOC_ATTEMPT_NOTES, the one build/ path the hook lets the agent write, must
    be <attempt dir>/notes.md (compared resolved, part by part with exact case), so the path
    the wrapper prints is the path the hook allows."""
    value = env.get(NOTES_ENV) or ""
    expected = attempt_dir / NOTES_FILE
    given = Path(value)
    if not value or (Path(roots.repo) / given).resolve().parts != expected.parts:
        raise AttemptError(f"{NOTES_ENV} must be set by the driver to {expected}, got {value!r}")
    return given


def _names(value: str, expected: Path, attempt_dir: Path, roots: Roots) -> bool:
    """Whether the driver's env `value` (absolute, or relative to the repository) names
    `expected`, a path below `attempt_dir`: resolved, part by part, and with the parts below the
    attempt directory spelled exactly as written (a case variant that a case-folding host would
    resolve onto `expected` is refused: the hook's view-unit and proposals shapes are exact)."""
    given = Path(roots.repo) / value
    tail = expected.relative_to(attempt_dir).parts
    written = Path(os.path.normpath(os.path.abspath(given))).parts
    return given.resolve().parts == expected.parts and written[-len(tail) :] == tail


def _unit_file(
    env: Mapping[str, str], roots: Roots, attempt_dir: Path, exe: str, unit: str
) -> Path | None:
    """D-24, T-07-31: REVERSEAPOC_UNIT_FILE, when set, must be the claim's own view unit
    <attempt dir>/view/src/<exe>/<unit>.c and exist, so a check never compiles another
    session's file. Unset (or empty, as the hook reads it) is a legacy session: None."""
    value = env.get(UNIT_FILE_ENV) or ""
    if not value:
        return None
    expected = attempt_dir / VIEW_DIR / VIEW_SRC / exe / f"{unit}.c"
    if not _names(value, expected, attempt_dir, roots) or not expected.is_file():
        raise AttemptError(f"{UNIT_FILE_ENV} must be set by the driver to {expected} (the "
                           f"claim's view unit, an existing file), got {value!r}")  # fmt: skip
    return expected


def _proposals(
    env: Mapping[str, str], roots: Roots, attempt_dir: Path, *, view: bool
) -> Path | None:
    """T-07-31: REVERSEAPOC_PROPOSALS must be <attempt dir>/proposals.jsonl (it need not
    exist yet), the one proposals path the hook lets the agent write. A view session must have
    it; a legacy session may leave it unset (None)."""
    value = env.get(PROPOSALS_ENV) or ""
    if not value and not view:
        return None
    expected = attempt_dir / PROPOSALS_FILE
    if not value or not _names(value, expected, attempt_dir, roots):
        raise AttemptError(f"{PROPOSALS_ENV} must be set by the driver to {expected}, "
                           f"got {value!r}")  # fmt: skip
    return expected


def _kind(env: Mapping[str, str], *, view: bool) -> str:
    """REVERSEAPOC_SESSION_KIND: absent is a matching session; otherwise exactly one of
    hooks.SESSION_KINDS (the hook denies any other value every write). A session other than
    matching checks only a view (the hook denies it every write without one)."""
    kind = env.get(SESSION_KIND_ENV)
    if kind is None:
        return SESSION_KINDS[0]
    if kind not in SESSION_KINDS:
        raise AttemptError(f"{SESSION_KIND_ENV}={kind!r} is not one of "
                           f"{', '.join(SESSION_KINDS)}")  # fmt: skip
    if kind != SESSION_KINDS[0] and not view:
        raise AttemptError(f"a {kind} session checks only its view, and {UNIT_FILE_ENV} is not "
                           "set")  # fmt: skip
    return kind


def src_root(claim: Claim, roots: Roots) -> Path:
    """The src tree the claim's check and pack read: the view's in view mode, else the shared
    one."""
    return claim.view_root / VIEW_SRC if claim.unit_file is not None else Path(roots.src)


def config_root(claim: Claim, roots: Roots) -> Path:
    """The config tree the claim's check reads: the view's in view mode, else the shared one."""
    return claim.view_root / VIEW_CONFIG if claim.unit_file is not None else Path(roots.config)


def unit_path(claim: Claim, roots: Roots) -> Path:
    """The claimed unit file a check compiles: the view unit in view mode, else src/'s."""
    if claim.unit_file is not None:
        return claim.unit_file
    return Path(roots.src) / claim.exe / f"{claim.unit}.c"


def _view_argv(claim: Claim, roots: Roots) -> tuple[str, ...]:
    """D-24 P7: check's five root options, each a repo-relative POSIX path under the view (the
    container runs from the repository root), so the check compiles this session's unit plus
    HEAD's other units and nothing another session wrote. Empty in legacy mode."""
    if claim.unit_file is None:
        return ()
    view, repo = claim.view_root, Path(roots.repo).resolve()
    paths = (("--src", view / VIEW_SRC), ("--config", view / VIEW_CONFIG),
             ("--cflags", view / VIEW_CFLAGS), ("--build", view / VIEW_BUILD),
             ("--log", view / VIEW_LOG))  # fmt: skip
    return tuple(item for flag, path in paths
                 for item in (flag, path.relative_to(repo).as_posix()))  # fmt: skip


# ---- attempt check ----


def container_prefix(attempt_dir: Path) -> str:
    """`reverseapoc-attempt-<8 hex>-`: the single source of an attempt's container names (fix
    round 2 N3). The hex is of sha256 of the RESOLVED attempt dir's POSIX path, so any spelling
    of the directory gives the same prefix; the 06-23 driver reuses this to remove a
    session's leftover containers."""
    resolved = Path(attempt_dir).resolve().as_posix()
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()
    return f"{CONTAINER_PREFIX}{digest[:_DIR_HEX]}-"


def container_name(claim: Claim, stem: str) -> str:
    """M7: container_prefix(attempt dir) + <NNNN>, unique per attempt and run, so a run the
    wrapper stopped (and the driver after a session, 06-23) can remove it by name."""
    return container_prefix(claim.attempt_dir) + stem


def container_check_argv(claim: Claim, *, sweep: bool, name: str, roots: Roots) -> tuple[str, ...]:
    """`check <claim> --json` in the container's `build` service, named `name` (-T: no tty, so
    the output is captured), plus `--sweep <function>` for the D-17 diagnostic. In view mode
    (D-24) the view's five roots come before --json; no agent argument ever chooses them."""
    argv = (*CONTAINER_RUN, "--name", name, *CONTAINER_CHECK, claim.target,
            *_view_argv(claim, roots), "--json")  # fmt: skip
    return (*argv, "--sweep", claim.function) if sweep else argv


@dataclass(frozen=True)
class CheckLogLine:
    """One line of checks.jsonl. best_percent, reloc_ok and bytes_ok are the claimed
    function's (a sweep: its best cell's). They are None (null) when the run printed no usable
    JSON (exit 2), and when the claimed function was not compiled: a stub, or absent from
    check's functions[] (exit 1, fix round 1 I1), or for a sweep that measured no cell (review
    IN-01). `sweep` is true for a sweep line, which is
    never the best C (06-23)."""

    n: int
    exit: int
    sweep: bool
    best_percent: float | None
    reloc_ok: bool | None
    bytes_ok: bool | None
    splice_ok: bool | None  # None for a sweep: it never lands
    sweep_hit: str | None  # "wcc386@V flags..." of a 100% cell under non-default flags
    source: str  # the C this run checked, relative to the attempt directory (F10)
    # 07-31 (ruling F11: defaults, after source): a readability check's readlint violations
    # (pending renames excluded, ruling F18) and accepted waivers; None for a matching or sweep
    # line, and when readlint itself failed (a tool line).
    readlint_violations: int | None = None
    readlint_waivers: int | None = None
    # 07.2-03 (ruling F11): a matching run's consumed note, checks/NNNN.note.json relative to the
    # attempt directory; None for a readability line. The window stays out of this log (gzv).
    note: str | None = None

    def to_json(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _parse(stdout: str) -> dict[str, Any] | None:
    try:
        doc = json.loads(stdout)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def _claimed(doc: Mapping[str, Any], claim: Claim) -> Mapping[str, Any] | None:
    for fn in doc["functions"]:
        if int(fn["va"], _HEX) == claim.address:
            return fn
    return None


def _passes(fn: Mapping[str, Any]) -> bool:
    """The claimed function's own verdict: objdiff 100, relocations and bytes ok."""
    perfect = float(fn["objdiff_percent"]) == PERFECT
    return perfect and fn["reloc"]["ok"] is True and fn["bytes"]["ok"] is True


def _verdict(doc: Mapping[str, Any], fn: Mapping[str, Any] | None, ran: Ran) -> int:
    """Fix round 1 I1(b): exit 0 only when check exited 0 (agreeing with its `ok`) and the
    claimed function itself passes. A claimed function check did not compile (still
    INCLUDE_ASM: a stub, or absent from functions[]) is 1, whatever the unit's verdict. An exit
    that disagrees with the JSON's `ok`, check's own 2 included, is 2."""
    ok = doc["ok"]
    if not isinstance(ok, bool):
        raise TypeError("ok is not a boolean")
    expected = EXIT_OK if ok else EXIT_MISMATCH
    if ran.returncode != expected:
        return EXIT_TOOL
    if fn is not None and ran.returncode == EXIT_OK and _passes(fn):
        return EXIT_OK
    return EXIT_MISMATCH


def _splices_ok(doc: Mapping[str, Any]) -> bool:
    splices = doc["splice"]
    return bool(splices) and all(s["ok"] is True for s in splices)


def _unit_passes(doc: Mapping[str, Any]) -> bool:
    """D-17: every function the check compiled passes and every splice is identical; a
    readability edit may not move any function's bytes, the claimed one or another."""
    return all(_passes(fn) for fn in doc["functions"]) and _splices_ok(doc)


def _check_line(
    doc: Mapping[str, Any], claim: Claim, ran: Ran, n: int, source: str, *,
    whole_unit: bool = False,
) -> CheckLogLine:  # fmt: skip
    """A line for a plain check. A claimed function that was not compiled carries no
    measurement (best_percent, reloc_ok and bytes_ok None). `whole_unit` (a readability check)
    also requires every other compiled function and every splice to pass for exit 0."""
    fn = _claimed(doc, claim)
    verdict = _verdict(doc, fn, ran)
    if whole_unit and verdict == EXIT_OK and not _unit_passes(doc):
        verdict = EXIT_MISMATCH
    return CheckLogLine(
        n, verdict, False,
        float(fn["objdiff_percent"]) if fn else None,
        fn["reloc"]["ok"] is True if fn else None,
        fn["bytes"]["ok"] is True if fn else None,
        _splices_ok(doc),
        None, source,
    )  # fmt: skip


def _measured(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cells = [c for c in doc["cells"] if c["status"] == MEASURED]
    return sorted(cells, key=lambda c: int(c["cell"]))


def _cell_spec(cell: Mapping[str, Any]) -> str:
    return " ".join([str(cell["compiler"]), *map(str, cell["flags"])])


def _is_hit(cell: Mapping[str, Any], default: str) -> bool:
    perfect = cell["objdiff_percent"] == PERFECT and cell["reloc_ok"] is True
    return perfect and cell["differing"] == 0 and _cell_spec(cell) != default


def _best_cell(cells: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """check.SweepCell.rank: a passing relocation check, then objdiff, then fewer bytes."""
    ranked = sorted(cells, key=lambda c: (c["reloc_ok"] is not True, -float(c["objdiff_percent"]),
                                          int(c["differing"])))  # fmt: skip
    return ranked[0] if ranked else None


def _stage2(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The measured cells of check's D-15 second stage (07-14); none when it did not run."""
    stage2 = doc.get("stage2")
    return _measured(stage2) if isinstance(stage2, Mapping) else []


def _sweep_line(
    doc: Mapping[str, Any], default: str, ran: Ran, n: int, source: str
) -> CheckLogLine:
    """best_* describe stage 1; sweep_hit is stage 1's first hit, else stage 2's (D-15)."""
    cells = _measured(doc)
    best = _best_cell(cells)
    hit = next((_cell_spec(c) for c in [*cells, *_stage2(doc)] if _is_hit(c, default)), None)
    return CheckLogLine(
        n, EXIT_OK if ran.returncode == EXIT_OK else EXIT_TOOL, True,
        float(best["objdiff_percent"]) if best else None,
        best["reloc_ok"] is True if best else None,
        best["differing"] == 0 if best else None,
        None, hit, source,
    )  # fmt: skip


def _default_spec(claim: Claim, roots: Roots) -> str:
    """The unit's own cflags.txt rule as a sweep cell names it: `wcc386@10.6 -4r -s -fpi`; in
    view mode the view's config/cflags.txt, the file the container check reads."""
    cflags = claim.view_root / VIEW_CFLAGS if claim.unit_file is not None else roots.cflags
    rule = select_rule(load_cflags(cflags), f"src/{claim.exe}/{claim.unit}.c")
    return " ".join([rule.spec, *rule.flags])


def _tool_line(n: int, sweep: bool, source: str) -> CheckLogLine:
    return CheckLogLine(n, EXIT_TOOL, sweep, None, None, None, None, None, source)


def _tail(text: str) -> list[str]:
    return [f"  | {line}" for line in text.rstrip("\n").splitlines()[-_TAIL_LINES:]]


def _ok(value: object) -> str:
    return "ok" if value is True else "FAILED"


def _window_cell(cell: Mapping[str, Any] | None) -> str:
    if cell is None:
        return "-"
    text = f"{cell['va']}  {cell['mnemonic']} {cell['operands']}".rstrip()
    return f"{text}  (relocated)" if cell["relocated"] else text


def _window_lines(fn: Mapping[str, Any]) -> list[str]:
    """check's window (functions[].window): ours on the left, the original on the right, the
    first differing row marked `>`. Nothing for a function without one (bytes ok, or an older
    document)."""
    window = fn.get("window")
    if not window:
        return []
    ours = [_window_cell(row["ours"]) for row in window]
    width = max(len(text) for text in ours)
    lines = [f"    first difference at {fn['bytes']['first_va']}: ours | original"]
    for row, mine in zip(window, ours, strict=True):
        mark = "    > " if row["first"] else "      "
        lines.append(f"{mark}{mine:<{width}} | {_window_cell(row['original'])}".rstrip())
    return lines


# ---- the region board (07.2-05; 999.7) ----

BOARD_MIN_SIZE = 256  # the owner's line: the region board appears for a row of 256 B and up
BOARD_HEAD = f"    region board (0x{check.BOARD_REGION_BYTES:X} bytes per region):"


def _regions(fn: Mapping[str, Any]) -> list[int] | None:
    """check's functions[].bytes.regions (differing bytes per 0x100 region), or None for an
    older document without the key or a malformed value."""
    same = fn.get("bytes")
    regions = same.get("regions") if isinstance(same, Mapping) else None
    if not isinstance(regions, list) or not all(type(k) is int and k >= 0 for k in regions):
        return None
    return regions


def region_summary(fn: Mapping[str, Any]) -> str | None:
    """One check entry's regions as `regions 0:0 1:3 2:12` (region index: differing bytes), or
    None for an entry without them. 07.2-03 records this string in each check's observed note
    (D-02), beside the exit, objdiff % and first difference."""
    regions = _regions(fn)
    if regions is None:
        return None
    return " ".join(["regions", *(f"{i}:{count}" for i, count in enumerate(regions))])


def _function_regions(doc: object, function: str) -> list[int] | None:
    """The regions of `function`'s entry (by name) in one check document, or None."""
    functions = doc.get("functions") if isinstance(doc, Mapping) else None
    for fn in functions if isinstance(functions, list) else ():
        if isinstance(fn, Mapping) and fn.get("name") == function:
            return _regions(fn)
    return None


_SAVED_SOURCE = re.compile(rf"{CHECKS_DIR}/{_SNAPSHOT.pattern}")  # checks/NNNN.c, as logged


def _plain_runs(attempt_dir: Path) -> Iterator[int]:
    """The run numbers of the plain checks in checks.jsonl: a line whose `sweep` is false (the
    test driver.read_checks tells sweeps apart by) and whose source is this attempt's own
    checks/NNNN.c. Malformed lines are skipped: the board only advises."""
    log = attempt_dir / CHECK_LOG
    if not log.is_file():
        return
    for raw in log.read_text(encoding="utf-8", errors="replace").splitlines():
        line = _parse(raw)
        if line is None or line.get("sweep") is not False:
            continue
        source = line.get("source")
        match = _SAVED_SOURCE.fullmatch(source) if isinstance(source, str) else None
        if match is not None:
            yield int(match.group(1))


def _saved_regions(attempt_dir: Path, function: str) -> Iterator[tuple[int, list[int]]]:
    """(run number, regions) of `function` in each plain check this attempt saved under
    <attempt dir>/checks/. A missing, malformed or tool-error document, or one without
    regions, is skipped."""
    for n in dict.fromkeys(_plain_runs(attempt_dir)):
        path = attempt_dir / CHECKS_DIR / f"{n:04d}.json"
        if not path.is_file():
            continue
        regions = _function_regions(_parse(path.read_text(encoding="utf-8", errors="replace")),
                                    function)  # fmt: skip
        if regions is not None:
            yield n, regions


def _board_row(index: int, count: int, n: int) -> str:
    low = index * check.BOARD_REGION_BYTES
    bounds = f"0x{low:03X}-0x{low + check.BOARD_REGION_BYTES - 1:03X}"
    if count == 0:
        return f"    {bounds}  exact in {n:04d}"
    return f"    {bounds}  closest {n:04d} ({count} differ)"


def region_board(
    attempt_dir: Path, claim: Claim, size: int, *,
    current: tuple[int, Mapping[str, Any]] | None = None,
) -> list[str]:  # fmt: skip
    """The region board of a claimed row of `size` bytes (none under BOARD_MIN_SIZE): per
    0x100 region from the row start, the plain check of this attempt with the fewest differing
    bytes there, "exact in NNNN" at 0, else "closest NNNN (k differ)"; ties go to the earliest.
    The checks are the ones the wrapper saved in <attempt dir>/checks/, plus `current`, the run
    being summarised as (number, document), which is not saved yet when the summary is built.
    Only the region counts check recorded are read: addresses on an implicit grid, never a
    byte. Earlier attempts are not read: the context pack carries their notes."""
    if size < BOARD_MIN_SIZE:
        return []
    entries = [(n, regions) for n, regions in _saved_regions(attempt_dir, claim.function)
               if current is None or n != current[0]]  # fmt: skip
    if current is not None:
        regions = _function_regions(current[1], claim.function)
        entries += [] if regions is None else [(current[0], regions)]
    if not entries:
        return []
    width = max(-(-size // check.BOARD_REGION_BYTES), *(len(r) for _, r in entries))
    lines = [BOARD_HEAD]
    for index in range(width):
        # Past a check's last region neither side has a byte there: 0 differ.
        count, best = min((r[index] if index < len(r) else 0, k) for k, r in entries)
        lines.append(_board_row(index, count, best))
    return lines


def _claimed_size(claim: Claim, roots: Roots) -> int:
    """The claimed row's size, from the functions.csv cmd_check validated the claim against."""
    row = claimed_row(read_functions_csv(config_root(claim, roots) / claim.exe / FUNCTIONS_CSV),
                      claim)  # fmt: skip
    return row.end - row.start


def _board(claim: Claim, n: int, doc: Mapping[str, Any]) -> list[str]:
    """The board for `attempt check`'s summary. A functions.csv or saved check that no longer
    reads is said in one line: the board only advises, and the run's evidence must still be
    saved (an error escaping here would turn the run into a tool error)."""
    try:
        return region_board(claim.attempt_dir, claim, _claimed_size(claim, ROOTS),
                            current=(n, doc))  # fmt: skip
    except (OSError, ValueError) as exc:
        return [f"    region board: not shown ({_one_line(exc)})"]


def _check_summary(
    doc: Mapping[str, Any], function: str | None = None, board: Sequence[str] = ()
) -> list[str]:
    """One line per function with its relocation problems and window; `board` (the region
    board) follows the window of `function`, the claimed one."""
    lines = []
    for fn in doc["functions"]:
        same = fn["bytes"]
        differ = "" if same["ok"] is True else f" ({same['differing']} differ)"
        reloc = _ok(fn["reloc"]["ok"])
        lines.append(f"  {fn['name']}  {fn['va']}  objdiff {fn['objdiff_percent']:g}%  "
                     f"reloc {reloc}  bytes {_ok(same['ok'])}{differ}")  # fmt: skip
        lines += [f"    reloc: {problem}" for problem in fn["reloc"]["problems"]]
        lines += _window_lines(fn)
        if fn["name"] == function:
            lines += board
    lines += [f"  problem: {p['name']} {p['va'] or ''} {p['reason']}" for p in doc["problems"]]
    lines += [f"  stub: {s['name']} {s['va']}" for s in doc.get("stubs", ())]
    lines += [f"  splice {s['exe']} {_ok(s['ok'])}" for s in doc["splice"]]
    return lines


def _best_text(label: str, best: Mapping[str, Any]) -> str:
    text = (f"  {label} {int(best['cell']):02d}  {_cell_spec(best)}  objdiff "
            f"{best['objdiff_percent']:g}%  reloc {_ok(best['reloc_ok'])}  "
            f"differing {best['differing']}")  # fmt: skip
    if "first_va" not in best and "size" not in best:
        return text  # a cell from before 261109-gzv
    first_va, size = best.get("first_va"), best.get("size")
    return (f"{text}  first_va {'none' if first_va is None else first_va}  "
            f"size {'none' if size is None else size}")  # fmt: skip


def _sweep_summary(doc: Mapping[str, Any], line: CheckLogLine) -> list[str]:
    best = _best_cell(_measured(doc))
    lines = ["  a sweep is a diagnostic: it never lands and never edits config/cflags.txt"]
    if best is None:
        lines.append("  no cell was measured")
    else:
        lines.append(_best_text("best cell", best))
    stage2 = _best_cell(_stage2(doc))
    if stage2 is not None:
        lines.append(_best_text("stage 2 best cell", stage2))
    if line.sweep_hit:
        lines.append(f"  sweep hit: needs flags {line.sweep_hit} (the owner decides; "
                     "cflags.txt is owner-only)")  # fmt: skip
    return lines


_VERDICT = {EXIT_OK: "OK: the claimed function matches and its unit passes check",
            EXIT_MISMATCH: "MISMATCH", EXIT_TOOL: "TOOL ERROR"}  # fmt: skip
_SWEEP_VERDICT = {EXIT_OK: "SWEEP RAN (a diagnostic: never a match)", EXIT_TOOL: "TOOL ERROR"}
_READABILITY_VERDICT = {
    EXIT_OK: "OK: every function still matches, every splice is identical and readlint is clean",
    EXIT_MISMATCH: "FAILED: see the check and readlint lines (both must pass)",
    EXIT_TOOL: "TOOL ERROR",
}
_CHECK_HALF = {
    EXIT_OK: "  check: OK (every compiled function objdiff 100% with relocations and bytes ok, "
             "every splice identical)",
    EXIT_MISMATCH: "  check: FAILED (a function below 100%, a relocation or byte difference, or "
                   "a splice that differs)",
    EXIT_TOOL: "  check: TOOL ERROR",
}  # fmt: skip


# ---- the readability half (07-31; D-17, D-18, D-20) ----


RL01 = "RL01"  # readlint's placeholder rule: the one a rename proposal can settle
_DATA = re.compile(r"D_([0-9A-F]{8})")
_RENAMABLE = ((_FUNC, FUNC_KIND), (_DATA, DATA_KIND))  # placeholder -> the row kind it names


def _one_line(text: object) -> str:
    return " ".join(str(text).split())


@dataclass(frozen=True)
class Pending:
    """Ruling F18: an RL01 hit on a placeholder that the session's own valid rename proposal
    renames. The driver applies the proposal after the session and lints again at landing."""

    violation: Violation
    name: str


@dataclass(frozen=True)
class Lint:
    """readlint's result on a readability session's view unit, or the tool error that stopped
    it (`result` None: exit 2, fail closed). `failing` are the violations that count: all of
    them but the `pending` renames; `notes` say why proposals covered nothing."""

    result: ReadlintResult | None
    error: str | None = None
    failing: tuple[Violation, ...] = ()
    pending: tuple[Pending, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def exit(self) -> int:
        if self.result is None:
            return EXIT_TOOL
        return EXIT_MISMATCH if self.failing else EXIT_OK

    @property
    def violation_count(self) -> int | None:
        return None if self.result is None else len(self.failing)

    @property
    def waiver_count(self) -> int | None:
        return None if self.result is None else sum(self.result.waivers.values())

    def lines(self) -> list[str]:
        if self.result is None:
            return [f"  readlint: TOOL ERROR: {self.error}"]
        n, waived = len(self.failing), self.waiver_count
        counts = (f"{waived} waiver{'' if waived == 1 else 's'}, "
                  f"{sum(self.result.allowlisted.values())} allowlisted references")  # fmt: skip
        if self.pending:
            counts += f", {len(self.pending)} pending rename{'' if len(self.pending) == 1 else 's'}"
        head = (f"  readlint: clean, {counts}" if not n
                else f"  readlint: {n} violation{'' if n == 1 else 's'}, {counts}")  # fmt: skip
        return [head,
                *(f"    {v.path}:{v.line}: {v.rule} {v.message}" for v in self.failing),
                *(f"    pending rename: {p.violation.path}:{p.violation.line}: "
                  f"{_placeholder(p.violation)} -> {p.name} (your proposal; the driver applies "
                  "it after the session and lints again at landing)" for p in self.pending),
                *(f"    {note}" for note in self.notes)]  # fmt: skip


def lint_view(claim: Claim) -> Lint:
    """readlint on the claim's view unit, with the view's src/ and config/ as its roots (the
    tree the container check compiled). A unit readlint does not check (not matched in the
    view's status.csv) is a tool error: a readability verdict never passes unlinted. RL01 hits
    the session's own valid rename proposals cover are pending, not failing (ruling F18).

    07.2-07 (D-15): RL07 judges the renames on the readability diff against <attempt
    dir>/unit-base.c (the view unit at launch, written by the driver) when it exists; a pending
    rename is applied only after the session, so its old name's declaration line in the view
    needs the provenance marker (an RL07 violation otherwise)."""
    view = claim.view_root
    unit = unit_path(claim, ROOTS)
    roots = dict(src_root=view / VIEW_SRC, config_root=view / VIEW_CONFIG)
    try:
        result = run_readlint([unit], units=[claim.target], base_text=_unit_base(claim, unit),
                              **roots)  # fmt: skip
    except (ValueError, OSError) as exc:  # ReadlintError is a ValueError
        return Lint(None, _one_line(exc))
    if not result.files_checked:
        why = "; ".join(f"{s.path}: {s.reason}" for s in result.skipped) or "no file selected"
        return Lint(None, f"readlint checked no file ({why})")
    names, notes = _proposed_names(claim, result.violations)
    pending = tuple(Pending(v, names[key]) for v in result.violations
                    if (key := _renamable(v)) is not None and key in names)  # fmt: skip
    covered = {p.violation for p in pending}
    try:
        unmarked = unmarked_declarations(unit, {_placeholder(p.violation) for p in pending},
                                         **roots) if pending else ()  # fmt: skip
    except (ValueError, OSError) as exc:
        return Lint(None, _one_line(exc))
    failing = tuple(sorted({v for v in result.violations if v not in covered} | set(unmarked)))
    return Lint(result, failing=failing, pending=pending, notes=tuple(notes))


def _unit_base(claim: Claim, unit: Path) -> dict[str, str] | None:
    """RL07's base text of the view unit: <attempt dir>/unit-base.c, None when the driver wrote
    none (a matching session, or a check run outside a readability night)."""
    path = claim.attempt_dir / UNIT_BASE
    return {str(unit): check.read_source(path)} if path.is_file() else None


def _placeholder(violation: Violation) -> str:
    """The identifier an RL01 message names first (readlint: `<name> is a placeholder ...`)."""
    return violation.message.split(" ", 1)[0]


def _renamable(violation: Violation) -> tuple[str, int] | None:
    """(kind, address) of the row an RL01 hit's func_/D_ placeholder names; None for any other
    hit (FUN_, DAT_ and the like name no row a proposal can rename)."""
    if violation.rule != RL01:
        return None
    word = _placeholder(violation)
    for pattern, kind in _RENAMABLE:
        if (found := pattern.fullmatch(word)) is not None:
            return kind, int(found.group(1), _HEX)
    return None


def _proposed_names(
    claim: Claim, violations: Sequence[Violation]
) -> tuple[dict[tuple[str, int], str], list[str]]:
    """(kind, address) -> name of the session's valid rename proposals for rows its RL01 hits
    name (the last proposal for a row wins, as the driver applies them in order), and notes on
    proposals that cover nothing. Unreadable proposals cover nothing (fail closed)."""
    wanted = {key for v in violations if (key := _renamable(v)) is not None}
    if not wanted or claim.proposals is None:
        return {}, []
    try:
        latest = {(p.kind, p.address): p for p in read_proposals(claim.proposals)
                  if isinstance(p, Rename) and p.exe == claim.exe
                  and (p.kind, p.address) in wanted}  # fmt: skip
        state = _naming_state(claim) if latest else {}
        problems = {key: rename_problem(p, data_ranges=[(p.address, p.address + 1)], **state)
                    for key, p in latest.items()}  # fmt: skip
    except (ValueError, OSError) as exc:  # ProposalError, UnitDefsError, FunctionsError
        return {}, [f"{PROPOSALS_FILE}: {_one_line(exc)}; no pending rename counted"]
    names = {key: p.name for key, p in latest.items() if problems[key] is None}
    notes = [f"rename proposal refused: {problem}" for problem in problems.values() if problem]
    return names, notes


def _naming_state(claim: Claim) -> dict[str, Any]:
    """rename_problem's naming state, from the view: its config's symbols.csv and functions.csv
    (runtime rows included) and the function definitions of its src/ units. The EXE's data
    objects are not read on the host: a data rename is checked against the D_ placeholder's own
    address, and the driver checks every proposal against the full state at landing (07-34)."""
    config = claim.view_root / VIEW_CONFIG / claim.exe
    symbols = config / SYMBOLS_CSV
    return {"symbols": read_symbols_csv(symbols) if symbols.exists() else [],
            "functions": read_functions_csv(config / FUNCTIONS_CSV), "runtime_names": (),
            "src_names": _src_names(claim)}  # fmt: skip


def _src_names(claim: Claim) -> dict[str, str]:
    """Function name -> view unit defining it, over the view's src/<exe>/ units, read through
    configure's translation phases like readlint (unitdefs.file_scope_definitions)."""
    cfg = unitdefs.load_configure(REPO_ROOT / unitdefs.CONFIGURE)
    names: dict[str, str] = {}
    for path in sorted((claim.view_root / VIEW_SRC / claim.exe).glob("*.c")):
        code = cfg.code_text(check.read_source(path))
        for name in unitdefs.file_scope_definitions(code):
            names.setdefault(name, f"src/{claim.exe}/{path.name}")
    return names


def _combined(check_exit: int, lint: Lint) -> int:
    """Both halves must pass: a tool error in either is 2, else a failure in either is 1."""
    codes = (check_exit, lint.exit)
    if EXIT_TOOL in codes:
        return EXIT_TOOL
    return EXIT_MISMATCH if EXIT_MISMATCH in codes else EXIT_OK


def _not_compiled(claim: Claim) -> str:
    return f"  {claim.function} was not compiled (still INCLUDE_ASM?)"


def _summary(
    claim: Claim, line: CheckLogLine, doc: Mapping[str, Any] | None, ran: Ran, seconds: float,
    *, lint: Lint | None = None, check_exit: int | None = None,
) -> str:  # fmt: skip
    """The printed summary; `check_exit` is the container half's exit when `lint` (a
    readability check) combined it with readlint's into line.exit."""
    check_exit = line.exit if check_exit is None else check_exit
    kind = "check --sweep" if line.sweep else "check"
    table = _SWEEP_VERDICT if line.sweep else _READABILITY_VERDICT if lint else _VERDICT
    head = (f"attempt {kind} {line.n}/{CHECK_BUDGET}, {round(seconds)} s "
            f"({CHECK_BUDGET - line.n} left) {claim.target} {claim.function}: "
            f"exit {line.exit} {table[line.exit]}")  # fmt: skip
    body = []
    if doc is not None and line.sweep:
        body = _sweep_summary(doc, line)
    elif doc is not None:
        missing = [_not_compiled(claim)] if _claimed(doc, claim) is None else []
        board = _board(claim, line.n, doc)
        body = missing + _check_summary(doc, claim.function, board)
    else:
        body = ["  the check printed no usable JSON"] + _tail(ran.stdout)
    if check_exit == EXIT_TOOL or doc is None:
        body += _tail(ran.stderr)
    if lint is not None:
        body = [_CHECK_HALF[check_exit], *body, *lint.lines()]
    source = claim.attempt_dir / line.source
    saved = (f"saved {source.with_suffix('.json').as_posix()} (full JSON) and "
             f"{source.as_posix()} (the C checked)\n"
             f"notes: {claim.notes.as_posix()}")  # fmt: skip
    return "\n".join([head, *body, saved])


def _append(log: Path, line: CheckLogLine) -> None:
    with log.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(line.to_json(), sort_keys=True) + "\n")


@dataclass
class _Held:
    """The held check lock; `keep` leaves it in place when the run ends (M7: an orphan
    container that could not be removed ends this attempt's checks)."""

    path: Path
    keep: bool = False


@contextmanager
def _check_lock(attempt_dir: Path) -> Iterator[_Held]:
    """Hold <attempt dir>/check.lock (O_CREAT|O_EXCL) for one whole run (security finding 1:
    a session can start checks with Bash run_in_background, and each would read the same
    count). Held already: AttemptError at once. A stale lock (a killed run) is never cleared:
    every session gets a fresh attempt directory, so it ends this attempt's checks."""
    lock = attempt_dir / CHECK_LOCK
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise AttemptError(f"another check is running in this attempt ({lock} exists; run "
                           "checks one at a time, in the foreground)") from exc  # fmt: skip
    held = _Held(lock)
    try:
        try:
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        finally:
            os.close(fd)
        yield held
    finally:
        if not held.keep:
            lock.unlink(missing_ok=True)


def _reserved(checks: Path) -> int:
    """The highest run number reserved in checks/ (a NNNN.c snapshot), 0 for none. A slot
    counts whether or not its run finished or logged a line."""
    numbers = [int(m.group(1)) for p in checks.iterdir() if (m := _SNAPSHOT.fullmatch(p.name))]
    return max(numbers, default=0)


def _reserve(path: Path, text: bytes) -> None:
    """Create the run's snapshot with O_EXCL: the file is the slot (ruling F10)."""
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | _O_BINARY, 0o644)
    except FileExistsError as exc:
        raise AttemptError(f"{path} is already reserved") from exc
    with os.fdopen(fd, "wb") as fh:
        fh.write(text)


def run_check(claim: Claim, *, sweep: bool, runner: Runner, roots: Roots) -> tuple[int, str]:
    """One check run of the claimed unit: (exit code 0/1/2, the summary to print). Under the
    attempt's check lock, the budget is checked and the run's slot reserved (its snapshot of
    the unit file) before the container starts."""
    with _check_lock(claim.attempt_dir) as held:
        return _locked_check(claim, sweep=sweep, runner=runner, roots=roots, held=held)


def _remove_container(name: str, runner: Runner, held: _Held) -> list[str]:
    """M7: after a timeout, `docker rm -f <name>` through the same runner, for at most
    RM_TIMEOUT seconds (N2). The caller has already marked the lock kept (N7); only a removal
    that succeeded clears the mark. If it fails, is slow or raises, the lock stays: the orphan
    may still write build/, so this attempt's checks end."""
    try:
        removed = runner(("docker", "rm", "-f", name), timeout=RM_TIMEOUT).returncode == EXIT_OK
    except Exception:  # noqa: BLE001 - any failure to remove it fails closed
        removed = False
    if removed:
        held.keep = False
        return [f"  the stopped container {name} was removed"]
    held.keep = True
    return [f"  the stopped container {name} could not be removed: the check lock stays and "
            "this attempt's checks are over; write notes.md and stop"]  # fmt: skip


def _locked_check(
    claim: Claim, *, sweep: bool, runner: Runner, roots: Roots, held: _Held
) -> tuple[int, str]:
    log = claim.attempt_dir / CHECK_LOG
    checks = claim.attempt_dir / CHECKS_DIR
    checks.mkdir(exist_ok=True)
    n = _reserved(checks) + 1
    if n > CHECK_BUDGET:
        raise AttemptError(f"check budget used: {CHECK_BUDGET} check runs in this attempt "
                           "(D-07); write notes.md and stop")  # fmt: skip
    note = _plan_and_note(claim, roots)  # D-01: refused here, no checks/NNNN.c exists yet
    default = _default_spec(claim, roots) if sweep else ""
    unit = unit_path(claim, roots)
    try:
        text = unit.read_bytes()
    except OSError as exc:
        raise AttemptError(f"{unit} cannot be read: {exc}") from exc
    stem = f"{n:04d}"
    source = f"{CHECKS_DIR}/{stem}.c"
    _reserve(claim.attempt_dir / source, text)
    name = container_name(claim, stem)
    started = CLOCK()
    ran = runner(container_check_argv(claim, sweep=sweep, name=name, roots=roots))
    seconds = CLOCK() - started
    if ran.timed_out:
        held.keep = True  # N7: fail closed from here until a removal succeeds
    removal: list[str] = []
    try:
        # 07-31: the readability half, in the same run and slot (one budget step).
        lint = lint_view(claim) if claim.kind == READABILITY and not sweep else None
        line, summary = _record(claim, ran, n, source, seconds, sweep=sweep, default=default,
                                saved_path=checks / f"{stem}.json", log=log, lint=lint,
                                note=note)  # fmt: skip
        if note is not None:  # consumed: the next check needs a new note (D-02)
            (claim.attempt_dir / CHECK_NOTE_NAME).unlink(missing_ok=True)
    finally:
        # N2: the evidence is written first, so a slow removal cannot lose it; N7: the
        # removal still runs when that write raised (whose error then surfaces as exit 2).
        if ran.timed_out:
            removal = _remove_container(name, runner, held)
    return line.exit, "\n".join([summary, *removal])


def _record(
    claim: Claim, ran: Ran, n: int, source: str, seconds: float, *, sweep: bool, default: str,
    saved_path: Path, log: Path, lint: Lint | None = None,
    note: Mapping[str, str] | None = None,
) -> tuple[CheckLogLine, str]:
    """The run's log line and summary, with its JSON saved and its line appended. With `lint`
    (a readability check) the line's exit is both halves combined. With `note` (a matching
    check's validated check-note.json) checks/NNNN.note.json is written before the line, which
    then points at it."""
    doc = _parse(ran.stdout)
    try:
        if doc is None:
            raise ValueError("no JSON")
        whole_unit = lint is not None
        line = (_sweep_line(doc, default, ran, n, source) if sweep
                else _check_line(doc, claim, ran, n, source, whole_unit=whole_unit))  # fmt: skip
        line, summary = _finish(claim, line, doc, ran, seconds, lint)
    except (KeyError, TypeError, ValueError, AttributeError):
        doc = None
        line, summary = _finish(claim, _tool_line(n, sweep, source), None, ran, seconds, lint)
    saved = doc if doc is not None else {"error": "no usable JSON", "returncode": ran.returncode,
                                         "stdout": ran.stdout, "stderr": ran.stderr}  # fmt: skip
    write_atomic(saved_path, (json.dumps(saved, indent=2) + "\n").encode("utf-8"))
    if note is not None:
        line = dataclasses.replace(line, note=_write_note(claim, line, doc, note))
    _append(log, line)
    return line, summary


def _finish(
    claim: Claim, line: CheckLogLine, doc: Mapping[str, Any] | None, ran: Ran, seconds: float,
    lint: Lint | None,
) -> tuple[CheckLogLine, str]:  # fmt: skip
    """The line and summary of a run; a readability check's line takes the combined exit."""
    if lint is None:
        return line, _summary(claim, line, doc, ran, seconds)
    combined = dataclasses.replace(line, exit=_combined(line.exit, lint),
                                   readlint_violations=lint.violation_count,
                                   readlint_waivers=lint.waiver_count)  # fmt: skip
    return combined, _summary(claim, combined, doc, ran, seconds, lint=lint, check_exit=line.exit)


CLAIMABLE_KINDS = (KIND_GAME, KIND_THUNK)  # the rows check requires a unit to account for


def claimed_row(rows: Sequence[FunctionRow], claim: Claim) -> FunctionRow:
    """Fix round 1 I1(a): the claimed function's functions.csv row, which must be a game or
    thunk row of the claimed unit (the rows check accounts for); AttemptError otherwise, so
    a check of a unit that does not hold the function never runs."""
    for row in rows:
        if row.start != claim.address:
            continue
        if row.unit == claim.unit and row.kind in CLAIMABLE_KINDS:
            return row
        raise AttemptError(f"{claim.function} is a {row.kind} row of unit {row.unit!r}, not a "
                           f"game or thunk row of the claimed {claim.target}")  # fmt: skip
    raise AttemptError(f"{claim.function} is no functions.csv row of {claim.exe}")


def cmd_check(*, sweep: bool) -> int:
    claim = Claim.from_env(os.environ, roots=ROOTS)
    claimed_row(read_functions_csv(config_root(claim, ROOTS) / claim.exe / FUNCTIONS_CSV), claim)
    code, text = run_check(claim, sweep=sweep, runner=RUNNER, roots=ROOTS)
    print(text)
    return code


# ---- the give-up record (07.2-02, 999.5; D-04, D-26: a file, not flags) ----


def _giveup_text_problem(value: object) -> str:
    """Why a give-up text is refused, or ''."""
    if not isinstance(value, str) or not value.strip():
        return "must be a non-empty string"
    if len(value) > GIVEUP_TEXT_CAP:
        return f"is {len(value)} characters, over the cap of {GIVEUP_TEXT_CAP}"
    found = next((char for char in _C_CHARS if char in value), None)
    if found is not None:
        return f"holds {found!r}: no C text in a give-up (D-04), describe it in words"
    if _LONG_HEX.search(value):
        return "holds a hex run of 65 or more characters (D-23)"
    return ""


def _session_object(path: Path, name: str, keys: Sequence[str]) -> dict:
    """A session file beside notes.md (giveup.json, plan.json, check-note.json) as one JSON
    object; AttemptError naming the file otherwise."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise AttemptError(f"no readable {path} ({type(exc).__name__}); write {name} beside "
                           "notes.md first") from None  # fmt: skip
    except ValueError as exc:
        raise AttemptError(f"{name} is not UTF-8 JSON: {_one_line(exc)}") from None
    if not isinstance(doc, dict):
        raise AttemptError(f"{name} must be one JSON object with exactly {', '.join(keys)}")
    return doc


def _exact_keys(doc: Mapping[str, Any], name: str, keys: Sequence[str]) -> None:
    """AttemptError naming what `doc` (from the file `name`) lacks or adds to exactly `keys`."""
    missing = [key for key in keys if key not in doc]
    if missing:
        raise AttemptError(f"{name} lacks {', '.join(missing)} (it holds exactly "
                           f"{', '.join(keys)})")  # fmt: skip
    extra = sorted(key for key in doc if key not in keys)
    if extra:
        raise AttemptError(f"{name} has the unknown key {', '.join(extra)} (it holds exactly "
                           f"{', '.join(keys)})")  # fmt: skip


def read_giveup(path: Path) -> dict:
    """The give-up a session wrote at `path` (D-04), the one validator of `attempt giveup` and
    the driver: a JSON object with exactly GIVEUP_KEYS, `category` one of GIVEUP_CATEGORIES, and
    each of GIVEUP_TEXTS a non-empty string of at most GIVEUP_TEXT_CAP characters with no `{`,
    `}` or `;` and no hex run of 65 or more. Returns the four fields; every problem raises
    AttemptError naming the field and the rule."""
    doc = _session_object(path, GIVEUP_NAME, GIVEUP_KEYS)
    _exact_keys(doc, GIVEUP_NAME, GIVEUP_KEYS)
    if not isinstance(doc["category"], str) or doc["category"] not in GIVEUP_CATEGORIES:
        raise AttemptError(f"{GIVEUP_NAME} category {doc['category']!r} is not one of "
                           f"{', '.join(GIVEUP_CATEGORIES)}")  # fmt: skip
    for key in GIVEUP_TEXTS:
        problem = _giveup_text_problem(doc[key])
        if problem:
            raise AttemptError(f"{GIVEUP_NAME} {key} {problem}")
    return {key: doc[key] for key in GIVEUP_KEYS}


def cmd_giveup() -> int:
    """`attempt giveup`: validate <attempt dir>/giveup.json (the notes file's sibling) and print
    what the driver will record. A matching session only (D-26); no check slot, no container."""
    claim = Claim.from_env(os.environ, roots=ROOTS)
    if claim.kind != SESSION_KINDS[0]:
        raise AttemptError(f"attempt giveup is a matching-session verb; a {claim.kind} session "
                           "leaves no give-up (D-26)")  # fmt: skip
    doc = read_giveup(claim.attempt_dir / GIVEUP_NAME)
    print(f"attempt giveup: accepted {doc['category']}")
    for key in GIVEUP_TEXTS:
        print(f"  {key}: {doc[key]}")
    return EXIT_OK


# ---- the plan and the check notes (07.2-03, 999.6; D-01..D-03, D-26: files, not flags) ----

PLAN_SMALL_SIZE = 64  # D-03: under 64 B one region covering the whole function is enough
NOTE_TEXT_CAP = 400  # no committed record holds these texts (the 200 cap does not bind); a bound
PLAN_LISTS = ("slots", "calls")
PLAN_KEYS = ("frame", *PLAN_LISTS, "regions")
REGION_KEYS = ("start", "end", "intent")
NOTE_KEYS = ("change", "why", "expect")
OBSERVED = "observed"  # D-02: what the check observed, written by the tool, never the session
NOTE_SUFFIX = ".note.json"  # checks/NNNN.note.json: a consumed check-note.json
_WINDOW_SIDES = ("ours", "original")


def _text_problem(value: object) -> str:
    """Why a plan or note text is refused, or ''."""
    if not isinstance(value, str) or not value.strip():
        return "must be a non-empty string"
    if len(value) > NOTE_TEXT_CAP:
        return f"is {len(value)} characters, over the cap of {NOTE_TEXT_CAP}"
    return ""


def _plan_texts(value: object, key: str) -> list[str]:
    """plan.json's `slots` or `calls`: a list (possibly empty) of non-empty texts."""
    if not isinstance(value, list):
        raise AttemptError(f"{PLAN_NAME} {key} must be a list of strings (an empty list is fine)")
    for index, item in enumerate(value):
        problem = _text_problem(item)
        if problem:
            raise AttemptError(f"{PLAN_NAME} {key}[{index}] {problem}")
    return list(value)


def _plan_region(value: object, index: int) -> dict:
    """One `{"start", "end", "intent"}` of plan.json's regions: offsets from the row start,
    end after start."""
    name = f"{PLAN_NAME} regions[{index}]"
    if not isinstance(value, dict):
        raise AttemptError(f"{name} must be an object with exactly {', '.join(REGION_KEYS)}")
    _exact_keys(value, name, REGION_KEYS)
    start, end = value["start"], value["end"]
    if type(start) is not int or type(end) is not int or start < 0:
        raise AttemptError(f"{name} start and end must be byte offsets (integers from 0)")
    if end <= start:
        raise AttemptError(f"{name} end 0x{end:X} is not after its start 0x{start:X}")
    problem = _text_problem(value["intent"])
    if problem:
        raise AttemptError(f"{name} intent {problem}")
    return {key: value[key] for key in REGION_KEYS}


def _regions_needed(size: int) -> int:
    """D-03: one region under PLAN_SMALL_SIZE, else two, except where the region board's grid
    leaves no room for an inner boundary (a row of exactly 0x100 bytes)."""
    if size < PLAN_SMALL_SIZE:
        return 1
    blocks = -(-size // check.BOARD_REGION_BYTES)
    return min(2, blocks) if size >= BOARD_MIN_SIZE else 2


def _check_cover(regions: Sequence[Mapping[str, Any]], size: int) -> None:
    """D-03: the regions are sorted and contiguous from 0 to `size`, numerous enough, and at
    BOARD_MIN_SIZE and up every inner boundary is on the board's 0x100 grid."""
    edge = 0
    for index, region in enumerate(regions):
        if region["start"] != edge:
            what = "a gap" if region["start"] > edge else "an overlap"
            raise AttemptError(f"{PLAN_NAME} regions leave {what}: regions[{index}] starts at "
                               f"0x{region['start']:X}, not at 0x{edge:X} (D-03: sorted and "
                               "contiguous from 0)")  # fmt: skip
        edge = region["end"]
    if edge != size:
        verb = "run past" if edge > size else "do not reach"
        raise AttemptError(f"{PLAN_NAME} regions {verb} 0x{size:X}: the last end is 0x{edge:X} "
                           "(D-03: they cover the whole function)")  # fmt: skip
    off_grid = [r["start"] for r in regions[1:] if r["start"] % check.BOARD_REGION_BYTES]
    if size >= BOARD_MIN_SIZE and off_grid:
        raise AttemptError(f"{PLAN_NAME} region boundary 0x{off_grid[0]:X} is not a multiple of "
                           f"0x{check.BOARD_REGION_BYTES:X} (D-03: from {BOARD_MIN_SIZE} B the "
                           "regions line up with the region board)")  # fmt: skip
    needed = _regions_needed(size)
    if len(regions) < needed:
        raise AttemptError(f"{PLAN_NAME} has {len(regions)} region for a 0x{size:X}-byte "
                           f"function, which needs at least {needed} (D-03: one region is "
                           f"enough only under {PLAN_SMALL_SIZE} B)")  # fmt: skip


def read_plan(path: Path, size: int) -> dict:
    """The plan a matching session wrote at `path` for a claimed row of `size` bytes (D-03),
    the one validator of `attempt plan` and `attempt check`: a JSON object with exactly
    PLAN_KEYS, `frame` a non-empty text, `slots` and `calls` lists of non-empty texts, and
    `regions` a non-empty list of {start, end, intent} covering 0..size (`_check_cover`). Texts
    are capped at NOTE_TEXT_CAP. Every problem raises AttemptError naming the field."""
    doc = _session_object(path, PLAN_NAME, PLAN_KEYS)
    _exact_keys(doc, PLAN_NAME, PLAN_KEYS)
    problem = _text_problem(doc["frame"])
    if problem:
        raise AttemptError(f"{PLAN_NAME} frame {problem}")
    lists = {key: _plan_texts(doc[key], key) for key in PLAN_LISTS}
    if not isinstance(doc["regions"], list) or not doc["regions"]:
        raise AttemptError(f"{PLAN_NAME} regions must be a non-empty list of "
                           f"{{{', '.join(REGION_KEYS)}}} objects")  # fmt: skip
    regions = [_plan_region(value, index) for index, value in enumerate(doc["regions"])]
    _check_cover(regions, size)
    return {"frame": doc["frame"], **lists, "regions": regions}


def read_check_note(path: Path) -> dict:
    """The note a matching session writes at `path` before each check (D-01, D-02): exactly
    NOTE_KEYS, each a non-empty text of at most NOTE_TEXT_CAP. `observed` is refused by name,
    and so is any other key: the tool records what the check observed."""
    doc = _session_object(path, CHECK_NOTE_NAME, NOTE_KEYS)
    if OBSERVED in doc:
        raise AttemptError(f"{CHECK_NOTE_NAME} holds {OBSERVED}: the tool records what the check "
                           f"observed (D-02); write only {', '.join(NOTE_KEYS)}")  # fmt: skip
    _exact_keys(doc, CHECK_NOTE_NAME, NOTE_KEYS)
    for key in NOTE_KEYS:
        problem = _text_problem(doc[key])
        if problem:
            raise AttemptError(f"{CHECK_NOTE_NAME} {key} {problem}")
    return {key: doc[key] for key in NOTE_KEYS}


def _region_text(region: Mapping[str, Any]) -> str:
    return f"  0x{region['start']:03X}-0x{region['end'] - 1:03X}  {region['intent']}"


def cmd_plan() -> int:
    """`attempt plan`: validate <attempt dir>/plan.json (the notes file's sibling) against the
    claimed row's size and print the accepted regions. A matching session only (D-26); no check
    slot, no container."""
    claim = Claim.from_env(os.environ, roots=ROOTS)
    if claim.kind != SESSION_KINDS[0]:
        raise AttemptError(f"attempt plan is a matching-session verb; a {claim.kind} session "
                           "writes no plan (D-26)")  # fmt: skip
    plan = read_plan(claim.attempt_dir / PLAN_NAME, _claimed_size(claim, ROOTS))
    print("attempt plan: accepted")
    for region in plan["regions"]:
        print(_region_text(region))
    return EXIT_OK


def _plan_and_note(claim: Claim, roots: Roots) -> dict | None:
    """D-01, D-26: a matching check's plan, checked against the claimed row's size, and its
    note, validated after the budget test and before the slot is reserved, so a refusal uses no
    check. None for a readability check, which needs neither."""
    if claim.kind != SESSION_KINDS[0]:
        return None
    read_plan(claim.attempt_dir / PLAN_NAME, _claimed_size(claim, roots))
    return read_check_note(claim.attempt_dir / CHECK_NOTE_NAME)


def _insn_text(cell: object) -> dict | None:
    """A window cell's mnemonic and operands only (no address, no byte)."""
    if not isinstance(cell, Mapping):
        return None
    return {"mnemonic": cell.get("mnemonic"), "operands": cell.get("operands")}


def _first_row(fn: Mapping[str, Any] | None) -> dict | None:
    """The window row check marked `first` (the first difference), ours and the original."""
    window = fn.get("window") if fn is not None else None
    rows = window if isinstance(window, list) else []
    row = next((r for r in rows if isinstance(r, Mapping) and r.get("first") is True), None)
    return None if row is None else {side: _insn_text(row.get(side)) for side in _WINDOW_SIDES}


def _observed(doc: Mapping[str, Any] | None, claim: Claim, line: CheckLogLine) -> dict:
    """D-02: what the run observed, from its log line and the claimed function's entry of the
    check document; null where the run gave none (a tool error, a sweep's cells)."""
    fn = _claimed(doc, claim) if doc is not None and not line.sweep else None
    same = fn.get("bytes") if fn is not None else None
    same = same if isinstance(same, Mapping) else {}
    return {"exit": line.exit, "objdiff_percent": line.best_percent,
            "bytes_differing": same.get("differing"), "first_va": same.get("first_va"),
            "window_first_row": _first_row(fn),
            "regions": region_summary(fn) if fn is not None else None}  # fmt: skip


def _write_note(claim: Claim, line: CheckLogLine, doc: Mapping[str, Any] | None,
                note: Mapping[str, str]) -> str:  # fmt: skip
    """checks/NNNN.note.json with O_EXCL, never overwritten (T-07.2-07): the session's change,
    why and expect beside what the run observed. Returns its path relative to the attempt
    directory, for the log line."""
    rel = f"{CHECKS_DIR}/{line.n:04d}{NOTE_SUFFIX}"
    text = json.dumps({**note, OBSERVED: _observed(doc, claim, line)}, indent=2) + "\n"
    _reserve(claim.attempt_dir / rel, text.encode("utf-8"))
    return rel


# ---- listings and the context pack (attempt asm, attempt context, the context verb; D-13) ----

IDIOM_HEADINGS = ("Known idioms", "Relocation rules")  # the matching.md sections a pack holds
ATTEMPT_LOG = Path("progress") / "attempts.jsonl"  # the driver's tracked log (06-23)
MANUAL_RUN = "manual"  # build/driver/manual/<exe>/<func>/: packs built by hand
_SECTION = re.compile(r"(?m)^(?=## )")


def exe_inputs(exe: str, *, orig: Path, manifest: Path, config: Path) -> check.ExeInputs:
    """The EXE as check loads it (fix round 1 M12: one loader): checked against the manifest,
    with config/<exe>/functions.csv, units.csv and, when present, symbols.csv under `config`."""
    target = check.select_exe(load_manifest(manifest), exe, manifest)
    return check.load_exe(target, orig_dir=orig, manifest=manifest, config_root=config)


def placeholder(row: FunctionRow) -> str:
    """func_XXXXXXXX: the driver's directory name for a row (REVERSEAPOC_FUNC's form)."""
    return f"func_{row.start:08X}"


def resolve_row(data: check.ExeInputs, name: str) -> FunctionRow:
    """The row of `data` whose functions.csv name, C name or placeholder is `name`."""
    for row in data.rows:
        if name in (row.name, data.symbols.c_name(row.start), placeholder(row)):
            return row
    raise AttemptError(f"{name} is no functions.csv row of {data.stem}")


def listing_path(data: check.ExeInputs, row: FunctionRow, asm_root: Path) -> Path:
    """The listing of `row` under `asm_root`: the file listing_text reads and the cache digests."""
    return Path(asm_root) / data.stem / asm.file_name(data.symbols, row)


def listing_text(data: check.ExeInputs, row: FunctionRow, asm_root: Path) -> str:
    path = listing_path(data, row, asm_root)
    if not path.is_file():
        raise AttemptError(f"no listing {path}; the owner writes them with "
                           f"`uv run reverseapoc asm {data.stem}`")  # fmt: skip
    return path.read_text(encoding="utf-8")


def idioms(text: str | None) -> str | None:
    """The IDIOM_HEADINGS sections of docs/matching.md, picked by heading."""
    if text is None:
        return None
    def wanted(part: str) -> bool:
        return part.startswith("## ") and part[3:].partition("\n")[0].strip() in IDIOM_HEADINGS

    parts = [part.rstrip("\n") for part in _SECTION.split(text) if wanted(part)]
    return "\n\n".join(parts) + "\n" if parts else None


_FUNC_PLACEHOLDER = re.compile(r"func_([0-9A-F]{8})")


def _attempt_docs(log: Path, stem: str, func: str) -> list[dict]:
    """This function's attempt records, oldest first: those naming `func`, and, when `func` is
    its func_ placeholder (the driver's attempt directories keep it), those naming its start.
    v2 records name the C name (07-23), so after a D-19 rename one function's records carry
    two names (ruling note, 07-34)."""
    if not log.is_file():
        return []
    found = _FUNC_PLACEHOLDER.fullmatch(func)
    start = f"0x{found.group(1)}" if found else None
    records = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or record.get("kind") != "attempt":
            continue
        same = record.get("function") == func or (start is not None
                                                  and record.get("start") == start)
        if record.get("exe") == stem and same:
            records.append(record)
    return records


def _giveup_line(record: Mapping) -> str | None:
    """One pack line of a committed record's give-up (07.2-02), each text on one line as the
    pack shows C heads; None for a record without a give-up object."""
    giveup = record.get("giveup")
    if not isinstance(giveup, dict):
        return None
    texts = {key: contextpack.one_line(str(giveup.get(key))) for key in GIVEUP_TEXTS}
    best = giveup.get("best_code") or "none"
    return (f"{record.get('run')} attempt {record.get('attempt')}: {giveup.get('category')}; "
            f"still differs: {texts['still_differs']}; suspected: {texts['suspected_cause']}; "
            f"best {best}")  # fmt: skip


_RUN_DIR = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")  # a run id as a build/driver/ directory
_UNIT_NAME = re.compile(r"[a-z0-9_]+")
_START = re.compile(r"0x([0-9A-F]{8})")


def _best_path(driver: Path, stem: str, record: Mapping) -> Path | None:
    """<driver>/<run>/<exe>/func_<start>/attempt-<n>/best/<unit>.c of a committed record (the
    driver's _best_file), or None when a field cannot name that path."""
    run, start, unit, n = (record.get(key) for key in ("run", "start", "unit", "attempt"))
    if not (isinstance(run, str) and _RUN_DIR.fullmatch(run) and ".." not in run):
        return None
    found = _START.fullmatch(start) if isinstance(start, str) else None
    if found is None or not isinstance(unit, str) or not _UNIT_NAME.fullmatch(unit):
        return None
    if type(n) is not int:
        return None
    return driver / run / stem / f"func_{found.group(1)}" / f"attempt-{n}" / "best" / f"{unit}.c"


def _percent(record: Mapping) -> float | None:
    check_field = record.get("check")
    value = check_field.get("best_percent") if isinstance(check_field, dict) else None
    number = isinstance(value, int | float) and not isinstance(value, bool)
    return float(value) if number else None


def _best_definition(driver: Path, stem: str, record: Mapping) -> str | None:
    """The record's function as its best/<unit>.c defines it (contextpack.definitions under
    the record's C name), or None: no such file, not UTF-8, or no such definition."""
    path = _best_path(driver, stem, record)
    if path is None or not path.is_file():
        return None
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    found = contextpack.definitions(text).get(str(record.get("function")))
    return found.source if found is not None else None


def _earlier_best_c(driver: Path, stem: str, records: Sequence[Mapping]) -> str | None:
    """07.2-02: the definition from the record with the highest check.best_percent (ties: the
    latest) whose best/<unit>.c gives one; a record without a readable one is skipped."""
    ranked = [(percent, index) for index, record in enumerate(records)
              if (percent := _percent(record)) is not None]  # fmt: skip
    for _percent_value, index in sorted(ranked, reverse=True):
        source = _best_definition(driver, stem, records[index])
        if source is not None:
            return source
    return None


def earlier_notes(repo: Path, stem: str, func: str) -> contextpack.Notes | None:
    """Ruling F9: build/driver/*/<exe>/<func>/attempt-*/notes.md (the driver's layout) and
    build/driver/*/<exe>/<func>/notes.md (manual packs), sorted by path, then this function's
    attempt records in progress/attempts.jsonl. 07.2-02 (999.5): from those records (the
    source of truth, not giveup.json files) the give-up lines, oldest first, and the earlier
    best C. Nothing is cut here: build_pack cuts notes only when the pack is over the cap (M11,
    records first, then the give-ups, then the oldest texts)."""
    driver = Path(repo).joinpath(*DRIVER_PARTS)
    found = {*driver.glob(f"*/{stem}/{func}/attempt-*/notes.md"),
             *driver.glob(f"*/{stem}/{func}/notes.md")}  # fmt: skip
    texts = []
    for path in sorted(found, key=lambda p: p.relative_to(driver).as_posix()):
        text = path.read_text(encoding="utf-8", errors="replace").rstrip("\n")
        texts.append(f"--- {path.relative_to(driver).as_posix()}\n{text}")
    docs = _attempt_docs(Path(repo) / ATTEMPT_LOG, stem, func)
    records = [json.dumps(record, sort_keys=True) for record in docs]
    giveups = tuple(line for record in docs if (line := _giveup_line(record)) is not None)
    best_c = _earlier_best_c(driver, stem, docs)
    if not texts and not records and not giveups and best_c is None:
        return None
    return contextpack.Notes(tuple(texts), tuple(records), f"--- {ATTEMPT_LOG.as_posix()}",
                             giveups, best_c)  # fmt: skip


def _unit_paths(src: Path, data: check.ExeInputs) -> dict[str, Path]:
    """The file of each unit a functions.csv row names, in sorted order: what _unit_texts reads
    and the context cache digests."""
    units = sorted({row.unit for row in data.rows if row.unit})
    return {unit: Path(src) / data.stem / f"{unit}.c" for unit in units}


def _unit_texts(src: Path, data: check.ExeInputs, claimed: str) -> dict[str, str]:
    """Every unit file of the EXE (06-13 note a: neighbours in other units need their C), read
    as bytes decoded as strict UTF-8 (note b: a lone CR stays refused, never translated). A
    unit that is not UTF-8 is left out, unless it is the claimed one."""
    texts = {}
    for unit, path in _unit_paths(src, data).items():
        if not path.is_file():
            continue
        try:
            texts[unit] = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            if unit == claimed:
                raise AttemptError(f"{path} is not UTF-8: {exc}") from exc
    return texts


def _optional_text(path: Path) -> str | None:
    return Path(path).read_text(encoding="utf-8") if Path(path).is_file() else None


def make_pack(
    data: check.ExeInputs,
    row: FunctionRow,
    *,
    src: Path,
    config: Path,
    asm_root: Path,
    roots: Roots,
    calls: contextpack.CallIndex | None = None,
) -> contextpack.Pack:
    """The D-13 pack of `row`: status from config/<exe>/status.csv, every unit text of the EXE,
    the listing and draft from asm/<exe>/ (and its ghidra/), include/common.h, the matching.md
    idioms and earlier notes. Pass `calls` to reuse one CallIndex across functions."""
    status = {entry.start: entry.status for entry in read_status(status_path(config, data.stem))}
    listing_dir = Path(asm_root) / data.stem
    inputs = contextpack.gather(
        row, rows=data.rows, flat=data.flat, fixups=data.fixups, symbols=data.symbols,
        status=status, unit_texts=_unit_texts(src, data, row.unit), listing_dir=listing_dir,
        draft_dir=listing_dir / ghidra.DRAFTS_DIR, common_h=_optional_text(roots.common_h),
        idioms=idioms(_optional_text(roots.matching)),
        notes=earlier_notes(roots.repo, data.stem, placeholder(row)), calls=calls,
    )  # fmt: skip
    return contextpack.build_pack(**inputs)


def _claimed_row(claim: Claim) -> tuple[check.ExeInputs, FunctionRow]:
    data = exe_inputs(claim.exe, orig=ROOTS.orig, manifest=ROOTS.manifest, config=ROOTS.config)
    return data, claimed_row(data.rows, claim)


def _register_notes(data: check.ExeInputs, row: FunctionRow) -> tuple[dict[int, str], str]:
    """The call notes of `row`, and the stderr text to print with them ("" when none). A lifter
    fault costs the notes and that one line, never the listing: past here cli's M9 handler
    would turn it into exit 2 in a live session."""
    try:
        return lift.call_notes(data, row), ""
    except Exception as exc:
        return {}, f"attempt asm: no call notes: {type(exc).__name__}: {_one_line(exc)}\n"


# ---- the per-view cache of attempt asm and attempt context (261109-gzw) ----


@dataclass(frozen=True)
class CacheKey:
    """Where one form's entry lives and what a hit must match: `facts` are values, `inputs` the
    digest of each file the form reads whose path is known before the EXE loads."""

    path: Path
    facts: dict[str, Any]
    inputs: dict[str, str | None]


def _digest(path: Path) -> str | None:
    """The sha256 hex of the file's bytes, or None when `path` is not a file."""
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _digests(paths: Iterable[Path]) -> dict[str, str | None]:
    return {Path(path).as_posix(): _digest(path) for path in paths}


def _tool_files() -> list[Path]:
    """The code an output depends on: every module of this package, the checkout's
    configure.py (contextpack.definitions loads it) and uv.lock (the locked dependencies)."""
    return [*sorted(Path(__file__).parent.glob("*.py")), REPO_ROOT / "configure.py",
            REPO_ROOT / "uv.lock"]  # fmt: skip


def _tool_version() -> str:
    """sha256 over the Python version, then each tool file's name and digest."""
    version = hashlib.sha256(sys.version.encode())
    for path in _tool_files():
        version.update(f"\0{path.name}\0{_digest(path)}".encode())
    return version.hexdigest()


def _entry_path(claim: Claim, form: str, name: str | None) -> Path:
    stem = form if name is None else f"{form}.{name}"
    return claim.view_root / VIEW_BUILD / CACHE_DIR / f"{stem}.json"


def _cache_key(claim: Claim, form: str, name: str | None) -> CacheKey | None:
    """The key of `form` (asm or context) with NAME `name`: exactly the inputs that form reads
    (RULINGS gzw and its amendment). None outside a view: a legacy session recomputes every
    time. Neither form reads the view's include/ or config/cflags.txt (only check and sweep
    compile), and asm never reads the view unit, so none of them is in a key."""
    if claim.unit_file is None:
        return None
    facts = {"format": CACHE_FORMAT, "form": form, "name": name, "exe": claim.exe,
             "unit": claim.unit, "function": claim.function, "tool": _tool_version()}  # fmt: skip
    target = check.select_exe(load_manifest(ROOTS.manifest), claim.exe, ROOTS.manifest)
    config = Path(ROOTS.config) / claim.exe
    paths = [Path(ROOTS.manifest), Path(ROOTS.orig) / target.name,
             *(config / table for table in (FUNCTIONS_CSV, UNITS_CSV, SYMBOLS_CSV))]  # fmt: skip
    if form == "context":
        facts["notes"] = _notes_digest(claim)
        paths += [status_path(ROOTS.config, claim.exe), ROOTS.common_h, ROOTS.matching]
    return CacheKey(_entry_path(claim, form, name), facts, _digests(paths))


def _notes_digest(claim: Claim) -> str:
    """The earlier notes and records make_pack packs, as earlier_notes reads them: the claimed
    row's placeholder is claim.function (claimed_row requires row.start == claim.address)."""
    notes = earlier_notes(ROOTS.repo, claim.exe, claim.function)
    return hashlib.sha256(repr(notes).encode()).hexdigest()


def _entry_valid(entry: Any, key: CacheKey) -> bool:
    if entry["facts"] != key.facts or entry["inputs"] != key.inputs:
        return False
    if not isinstance(entry["stdout"], str) or not isinstance(entry["stderr"], str):
        return False
    return all(_digest(Path(path)) == digest for path, digest in entry["derived"].items())


def _cache_hit(key: CacheKey) -> dict[str, Any] | None:
    """The stored entry when its facts and inputs equal the key's and every derived file still
    has the digest it had; else None. A missing entry, or one of another shape (a torn write),
    is a miss, as lift._read_census treats a torn census; any other error propagates."""
    if not key.path.is_file():
        return None
    try:
        entry = json.loads(key.path.read_text(encoding="utf-8"))
        return entry if _entry_valid(entry, key) else None
    except ValueError, KeyError, TypeError, AttributeError:
        return None


def _cache_store(key: CacheKey, derived: dict[str, str | None], stdout: str, stderr: str) -> None:
    """Keep one form's output. A fault costs the entry and one stderr line, never the output."""
    entry = {"facts": key.facts, "inputs": key.inputs, "derived": derived, "stdout": stdout,
             "stderr": stderr}  # fmt: skip
    try:
        key.path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(key.path, json.dumps(entry, sort_keys=True).encode("utf-8"))
    except OSError as exc:
        print(f"attempt {key.facts['form']}: cache not written: {type(exc).__name__}: "
              f"{_one_line(exc)}", file=sys.stderr)  # fmt: skip


def _lookup(claim: Claim, form: str, name: str | None) -> tuple[CacheKey | None, dict | None]:
    key = _cache_key(claim, form, name)
    return key, (_cache_hit(key) if key is not None else None)


def cmd_asm(name: str | None) -> int:
    """Print the claimed function's listing, or that of NAME (another row of the same EXE), with
    its notes on the lines they belong to. They reach the terminal only: D-05. A jump and a call
    never share an address, so the merge loses nothing. In a view a repeat whose inputs are
    unchanged prints the stored output without loading the EXE (261109-gzw)."""
    claim = Claim.from_env(os.environ, roots=ROOTS)
    key, entry = _lookup(claim, "asm", name)
    if entry is not None:
        sys.stderr.write(entry["stderr"])  # before the listing, as on a miss
        sys.stdout.write(entry["stdout"])
        return EXIT_OK
    data, row = _claimed_row(claim)
    if name is not None:
        row = resolve_row(data, name)
    read = [listing_path(data, row, ROOTS.asm)]
    if row.kind != KIND_DATA_IN_CODE:  # lift.call_notes returns before its census read
        read.append(lift._census_file(data.stem))
    derived = _digests(read)  # taken before the reads: a change mid-run is a later miss
    text = listing_text(data, row, ROOTS.asm)
    notes = asm.case_notes(row, flat=data.flat, fixups=data.fixups, rows=data.rows,
                           symbols=data.symbols)  # fmt: skip
    calls, line = _register_notes(data, row)
    out = asm.annotated(text, notes | calls)
    sys.stderr.write(line)  # the lifter's line comes before the listing, as before 261109-gzw
    sys.stdout.write(out)
    if key is not None:
        _cache_store(key, derived, out, line)
    return EXIT_OK


def cmd_context() -> int:
    """Rebuild the claimed function's pack into <attempt dir>/context.md and print it. In a view
    a repeat whose inputs are unchanged writes and prints the stored pack without loading the
    EXE (261109-gzw)."""
    claim = Claim.from_env(os.environ, roots=ROOTS)
    key, entry = _lookup(claim, "context", None)
    if entry is not None:
        text = entry["stdout"]
        # Claim.from_env proved the attempt dir an existing directory below build/driver/ with
        # exact case: write_pack's T-06-29 guard.
        path = claim.attempt_dir / contextpack.PACK_FILE
        write_atomic(path, text.encode("utf-8"))
        derived = None
    else:
        text, path, derived = _rebuild_pack(claim)
    sys.stdout.write(text)
    print(f"wrote {path.as_posix()}; notes: {claim.notes.as_posix()}", file=sys.stderr)
    if key is not None and derived is not None:
        _cache_store(key, derived, text, "")  # the `wrote` line is printed fresh each run
    return EXIT_OK


def _rebuild_pack(claim: Claim) -> tuple[str, Path, dict[str, str | None]]:
    """The pack built and written as before the cache, with the digests of the listing, the
    draft and every unit file it reads, taken before make_pack reads them."""
    data, row = _claimed_row(claim)
    src = src_root(claim, ROOTS)
    listing = listing_path(data, row, ROOTS.asm)
    read = [listing, listing.parent / ghidra.DRAFTS_DIR / ghidra.draft_name(row.start),
            *_unit_paths(src, data).values()]  # fmt: skip
    derived = _digests(read)
    pack = make_pack(data, row, src=src, config=ROOTS.config, asm_root=ROOTS.asm, roots=ROOTS)
    path = contextpack.write_pack(pack, claim.attempt_dir, root=ROOTS.repo)
    return pack.text, path, derived

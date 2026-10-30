# SPDX-License-Identifier: GPL-3.0-or-later
"""The attempt wrapper (D-44): the only commands a matching session runs through Bash.

`uv run --frozen reverseapoc attempt check|asm|context` is bound to the claimed function. The
claim comes only from the driver's environment (REVERSEAPOC_CLAIM, REVERSEAPOC_FUNC,
REVERSEAPOC_ATTEMPT_DIR), each validated here; no agent argument chooses the unit, the
function, the flags, the Watcom tree or the source root. The accepted argument shapes are
exactly hooks.ATTEMPT_FORMS (ruling F27), which the matching-session hook allows.

`attempt check` runs `reverseapoc check <claim> --json` in the container through an injectable
runner, at most CHECK_BUDGET times per attempt (D-07). One run at a time: each holds
`check.lock` and reserves its number by creating the snapshot of the C it checks
(`checks/NNNN.c`, ruling F10, O_EXCL), so a reserved slot counts even if the run then fails.
Each run keeps the JSON (`checks/NNNN.json`) and appends one line to `checks.jsonl`, all under
the gitignored attempt directory in build/driver/. `--sweep` runs the
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
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import asm, check, contextpack, unitdefs
from .cflags import DEFAULT_CFLAGS, load_cflags, select_rule
from .check import DEFAULT_CONFIG, DEFAULT_SRC, EXIT_MISMATCH, EXIT_OK, EXIT_TOOL, PERFECT
from .fileio import write_atomic
from .functions import (
    KIND_GAME,
    KIND_THUNK,
    FunctionRow,
    read_functions_csv,
    read_symbols_csv,
)
from .hooks import (
    ATTEMPT_FORMS,
    ATTEMPT_PREFIX,
    CLAIM_ENV,
    NOTES_ENV,
    PROPOSALS_ENV,
    SESSION_KIND_ENV,
    SESSION_KINDS,
    UNIT_FILE_ENV,
    attempt_form_matches,
)
from .proposals import Rename, read_proposals, rename_problem
from .readlint import ReadlintResult, Violation, run_readlint
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


def form_allowed(argv: Sequence[str]) -> bool:
    """Whether `argv` (after `attempt`) is one of hooks.ATTEMPT_FORMS (ruling F27)."""
    return attempt_form_matches(argv)


def forms_text() -> str:
    return "; ".join(" ".join((*ATTEMPT_PREFIX, *form)) for form in ATTEMPT_FORMS)


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


def _check_summary(doc: Mapping[str, Any]) -> list[str]:
    lines = []
    for fn in doc["functions"]:
        same = fn["bytes"]
        differ = "" if same["ok"] is True else f" ({same['differing']} differ)"
        reloc = _ok(fn["reloc"]["ok"])
        lines.append(f"  {fn['name']}  {fn['va']}  objdiff {fn['objdiff_percent']:g}%  "
                     f"reloc {reloc}  bytes {_ok(same['ok'])}{differ}")  # fmt: skip
        lines += [f"    reloc: {problem}" for problem in fn["reloc"]["problems"]]
    lines += [f"  problem: {p['name']} {p['va'] or ''} {p['reason']}" for p in doc["problems"]]
    lines += [f"  stub: {s['name']} {s['va']}" for s in doc.get("stubs", ())]
    lines += [f"  splice {s['exe']} {_ok(s['ok'])}" for s in doc["splice"]]
    return lines


def _best_text(label: str, best: Mapping[str, Any]) -> str:
    return (f"  {label} {int(best['cell']):02d}  {_cell_spec(best)}  objdiff "
            f"{best['objdiff_percent']:g}%  reloc {_ok(best['reloc_ok'])}  "
            f"differing {best['differing']}")  # fmt: skip


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
    the session's own valid rename proposals cover are pending, not failing (ruling F18)."""
    view = claim.view_root
    try:
        result = run_readlint([unit_path(claim, ROOTS)], src_root=view / VIEW_SRC,
                              config_root=view / VIEW_CONFIG, units=[claim.target])  # fmt: skip
    except (ValueError, OSError) as exc:  # ReadlintError is a ValueError
        return Lint(None, _one_line(exc))
    if not result.files_checked:
        why = "; ".join(f"{s.path}: {s.reason}" for s in result.skipped) or "no file selected"
        return Lint(None, f"readlint checked no file ({why})")
    names, notes = _proposed_names(claim, result.violations)
    pending = tuple(Pending(v, names[key]) for v in result.violations
                    if (key := _renamable(v)) is not None and key in names)  # fmt: skip
    covered = {p.violation for p in pending}
    failing = tuple(v for v in result.violations if v not in covered)
    return Lint(result, failing=failing, pending=pending, notes=tuple(notes))


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
        body = missing + _check_summary(doc)
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
                                saved_path=checks / f"{stem}.json", log=log,
                                lint=lint)  # fmt: skip
    finally:
        # N2: the evidence is written first, so a slow removal cannot lose it; N7: the
        # removal still runs when that write raised (whose error then surfaces as exit 2).
        if ran.timed_out:
            removal = _remove_container(name, runner, held)
    return line.exit, "\n".join([summary, *removal])


def _record(
    claim: Claim, ran: Ran, n: int, source: str, seconds: float, *, sweep: bool, default: str,
    saved_path: Path, log: Path, lint: Lint | None = None,
) -> tuple[CheckLogLine, str]:
    """The run's log line and summary, with its JSON saved and its line appended. With `lint`
    (a readability check) the line's exit is both halves combined."""
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


def listing_text(data: check.ExeInputs, row: FunctionRow, asm_root: Path) -> str:
    path = Path(asm_root) / data.stem / asm.file_name(data.symbols, row)
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


def _attempt_records(log: Path, stem: str, func: str) -> list[str]:
    if not log.is_file():
        return []
    records = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or record.get("kind") != "attempt":
            continue
        if record.get("exe") == stem and record.get("function") == func:
            records.append(json.dumps(record, sort_keys=True))
    return records


def earlier_notes(repo: Path, stem: str, func: str) -> contextpack.Notes | None:
    """Ruling F9: build/driver/*/<exe>/<func>/attempt-*/notes.md (the driver's layout) and
    build/driver/*/<exe>/<func>/notes.md (manual packs), sorted by path, then this function's
    attempt records in progress/attempts.jsonl. Nothing is cut here: build_pack cuts notes
    only when the pack is over the cap (M11, records first, then the oldest texts)."""
    driver = Path(repo).joinpath(*DRIVER_PARTS)
    found = {*driver.glob(f"*/{stem}/{func}/attempt-*/notes.md"),
             *driver.glob(f"*/{stem}/{func}/notes.md")}  # fmt: skip
    texts = []
    for path in sorted(found, key=lambda p: p.relative_to(driver).as_posix()):
        text = path.read_text(encoding="utf-8", errors="replace").rstrip("\n")
        texts.append(f"--- {path.relative_to(driver).as_posix()}\n{text}")
    records = _attempt_records(Path(repo) / ATTEMPT_LOG, stem, func)
    if not texts and not records:
        return None
    return contextpack.Notes(tuple(texts), tuple(records), f"--- {ATTEMPT_LOG.as_posix()}")


def _unit_texts(src: Path, data: check.ExeInputs, claimed: str) -> dict[str, str]:
    """Every unit file of the EXE (06-13 note a: neighbours in other units need their C), read
    as bytes decoded as strict UTF-8 (note b: a lone CR stays refused, never translated). A
    unit that is not UTF-8 is left out, unless it is the claimed one."""
    texts = {}
    for unit in sorted({row.unit for row in data.rows if row.unit}):
        path = Path(src) / data.stem / f"{unit}.c"
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
        draft_dir=listing_dir / "ghidra", common_h=_optional_text(roots.common_h),
        idioms=idioms(_optional_text(roots.matching)),
        notes=earlier_notes(roots.repo, data.stem, placeholder(row)), calls=calls,
    )  # fmt: skip
    return contextpack.build_pack(**inputs)


def _claimed_row() -> tuple[Claim, check.ExeInputs, FunctionRow]:
    claim = Claim.from_env(os.environ, roots=ROOTS)
    data = exe_inputs(claim.exe, orig=ROOTS.orig, manifest=ROOTS.manifest, config=ROOTS.config)
    return claim, data, claimed_row(data.rows, claim)


def cmd_asm(name: str | None) -> int:
    """Print the claimed function's listing, or that of NAME (another row of the same EXE)."""
    _, data, row = _claimed_row()
    if name is not None:
        row = resolve_row(data, name)
    sys.stdout.write(listing_text(data, row, ROOTS.asm))
    return EXIT_OK


def cmd_context() -> int:
    """Rebuild the claimed function's pack into <attempt dir>/context.md and print it."""
    claim, data, row = _claimed_row()
    pack = make_pack(data, row, src=src_root(claim, ROOTS), config=ROOTS.config,
                     asm_root=ROOTS.asm, roots=ROOTS)  # fmt: skip
    path = contextpack.write_pack(pack, claim.attempt_dir, root=ROOTS.repo)
    sys.stdout.write(pack.text)
    print(f"wrote {path.as_posix()}; notes: {claim.notes.as_posix()}", file=sys.stderr)
    return EXIT_OK

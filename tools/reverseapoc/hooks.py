# SPDX-License-Identifier: GPL-3.0-or-later
r"""Claude Code PreToolUse guardrail hooks (AGT-05, D-15..D-18, D-44..D-46, DI-07).

Run as `uv run --frozen --project "$CLAUDE_PROJECT_DIR" python -I -m reverseapoc.hooks
pre-tool-use --layer always|matching || exit 2` with the hook payload on stdin (the `|| exit 2`
turns a failure of uv or the import into a block, and each handler's `"timeout": 120,
"onFailure": "block"` turns a slow or hung run into one). Two layers:

- **always** (`.claude/settings.json`, every session in the repo, matcher
  `Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell`; the driver's copy keeps the edit matcher,
  since its matching layer handles Bash): blocks edits under orig/, asm/ and build/ (except the
  driver's per-session files at their shapes: REVERSEAPOC_ATTEMPT_NOTES, D-46, and its
  giveup.json, plan.json and check-note.json siblings, D-26, and the REVERSEAPOC_UNIT_FILE view
  unit and REVERSEAPOC_PROPOSALS
  file, D-24), of
  config/targets.toml, config/watcom.toml, any *.sha1 and the owner-only config/cflags.txt and
  config/cflags-proposals.toml (D-12, D-27 P3), and inline asm (`_asm`, `__asm`,
  `_Pragma`, a code-emitting `#pragma aux`) in src/, include/ and the view unit (D-16, P6).
  Every other path stays editable, so GSD executors and the owner keep working on tools/,
  tests/, configure.py, docs/ and .planning/. The worktree rule (261109-gzy): from a harness
  worktree cwd (.claude/worktrees/<name>/) it denies a Bash or PowerShell command, or a script
  the command names, that spells the main checkout's absolute path, and a script it cannot scan
  (named through shell expansion, not one text, written and run by the same command, or named
  beside a heredoc marker or a backslash-newline). A call that names a script passes only when
  every command in it has a listed shape, judged on its words as the shell resolves them
  (261112-fdw: a plain interpreter and a plain script path, the uv forms, listed git
  subcommands, read and print commands, assignments). Every other shell call gets no opinion.
  The drive write guard (todo drive-write-guard): while a live process holds a checkout's
  build/driver/drive.lock (locks.is_held; a stale lock file blocks nothing), a session without
  the driver's claim may not edit under that checkout, worktrees included. A shell call may
  not redirect into it, pass a git global option but -C, --no-optional-locks, --no-pager and
  -P, or run an encoded or unparseable nested command; and a call that runs in or names the
  checkout anywhere runs only listed read shapes (default deny: reads, find and sed in their
  reading shapes, git reads and `--no-optional-locks` status/diff, writers aimed outside it,
  `uv run --no-project python <script outside it>`); nested shells and eval are judged as
  calls of their own. cd and `git -C` move where a command runs, so the scratchpad-clone route
  the denial names stays open.
- **matching** (`config/driver/claude-settings.json`, matcher `*`, matching sessions only):
  denies by default (D-17). With the driver's REVERSEAPOC_CLAIM=<exe>/<unit> and
  REVERSEAPOC_UNIT_FILE (D-24) a session may write only its view unit, notes.md and
  proposals.jsonl, and a matching session also the giveup.json, plan.json and check-note.json
  beside its notes.md (07.2-02, 07.2-03, D-26) (`matching_write_allowed`, which the driver's
  audit reuses); without the unit
  file it writes nothing (07-13 removed the Phase 6 single-session allowlist of src/<exe>/<unit>.c
  and new include/*.h), with no `#pragma` of any kind during the pilot (D-18, 06-15 fix
  round 1 M14: `#pragma on/off (check_stack)` changes code the way a flag does); read only
  inside the repository and never a .env* file (a Glob pattern or Grep glob may hold plain
  {a,b} alternatives, each expansion judged by the same rule; [ ] classes are refused,
  261109-gzw), and, in a session of a non-Anthropic arm (REVERSEAPOC_EGRESS=1, 07.2-12, D-10),
  nothing under orig/ or third_party/; and run Bash only as an exact attempt-wrapper form
  (ATTEMPT_PREFIX plus one of `forms_for(kind)`: MATCHING_FORMS for a matching session,
  ATTEMPT_FORMS for a readability one, D-44, D-26), in the foreground (no `run_in_background`),
  and an `attempt check` only with the Bash tool's `timeout` at CHECK_TIMEOUT_MS (WR-04).
  Every other tool is denied. The always rules apply here too, so a
  matching session never depends on how Claude Code merges the two settings files.

`decide` is the pure decision; `main` reads stdin, prints the deny JSON and exits 0, or prints
nothing and exits 0 for no opinion (never an allow decision, so Claude Code's own permission rules
still bind). Any error exits 2 with the reason on stderr, which blocks the call (fail closed);
Claude Code treats every other exit code as non-blocking, so main never returns one.

Paths are normalised before any rule (`candidates`), `..` resolved and compared casefolded
(NTFS is case-insensitive). On an NT host every path is a Windows path: `/` becomes `\`, device
prefixes (`\\?\`, `\\.\`, `\??\`) and UNC are understood, a rooted path takes the cwd's drive,
Git Bash's `/c/...` is read both ways, and the host's realpath of the raw path is judged too
(it maps volume GUIDs, GLOBALROOT and 8.3 names to the drive path). A device path the host
cannot map to a drive or share is an error, so the call is blocked. A path is judged against
the project root ($CLAUDE_PROJECT_DIR, else the checkout holding this file) and against every
ancestor holding `.git` (a directory, or a worktree's file), so a `.git` planted inside the
checkout cannot move the root, and a worktree under .claude/worktrees/ is judged as its own
checkout too."""

from __future__ import annotations

import argparse
import codecs
import fnmatch
import io
import itertools
import json
import math
import ntpath
import os
import posixpath
import re
import shlex
import sys
import tokenize
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .locks import DRIVE_LOCK, is_held

EXIT_OK = 0
_GIT_TIMEOUT = 30  # seconds for `git ls-files`; each handler's own timeout is 120
EXIT_BLOCK = 2  # the only exit code besides 0 that Claude Code treats as blocking
LAYER_ALWAYS = "always"
LAYER_MATCHING = "matching"
LAYERS = (LAYER_ALWAYS, LAYER_MATCHING)
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SHELL_TOOLS = ("Bash", "PowerShell")  # judged only from a harness worktree (261109-gzy)
_PATH_FIELD = {"Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path",
               "NotebookEdit": "notebook_path"}  # fmt: skip

# D-16: the always-on layer's protected paths, repo-relative and casefolded.
_PROTECTED_DIRS = {
    "orig": "it holds the original game files the oracle compares against",
    "asm": "its listings are generated by `reverseapoc asm` and the Ghidra export",
    "build": "it is build output; write evidence there by shell redirection only",
}
_PROTECTED_FILES = {
    "config/targets.toml": "the hash manifest of the original executables",
    "config/watcom.toml": "the hash manifest of the Watcom toolchains",
    # D-27 P3: no exemption, since the owner's verbs write from Python and no hook sees them.
    "config/cflags.txt": (
        "it is owner-only (D-12, Phase 5 D-18); only `reverseapoc flags approve` or "
        "`reverseapoc flags default`, which the owner runs and which write from Python, change it"
    ),
    "config/cflags-proposals.toml": (
        "it is the D-12 proposal queue, written only by `reverseapoc flags` from Python; a "
        "session writes its proposals.jsonl instead"
    ),
}
_MANIFEST_SUFFIX = ".sha1"
_SCANNED_DIRS = ("src", "include")
# D-46: the one path under build/ the always layer lets through, set by the driver.
NOTES_ENV = "REVERSEAPOC_ATTEMPT_NOTES"
_NOTES_DIR = "build/driver"
_NOTES_NAME = "notes.md"
# 07.2-02 (999.5, D-04, D-26): a matching session's give-up record, the sibling of its notes.md.
GIVEUP_NAME = "giveup.json"
# 07.2-03 (999.6, D-01..D-03, D-26): its plan before code and its note before each check, the
# other siblings of notes.md; the wrapper validates them (attempt plan, attempt check).
PLAN_NAME = "plan.json"
CHECK_NOTE_NAME = "check-note.json"
SESSION_FILE_NAMES = (GIVEUP_NAME, PLAN_NAME, CHECK_NOTE_NAME)
# D-24 (P6): a session's private view unit and its proposals file, set per claude process by the
# driver. The always layer exempts them from build/ like the notes file, at these shapes only,
# and scans the unit file as it scans src/.
UNIT_FILE_ENV = "REVERSEAPOC_UNIT_FILE"
PROPOSALS_ENV = "REVERSEAPOC_PROPOSALS"
SESSION_KIND_ENV = "REVERSEAPOC_SESSION_KIND"
SESSION_KINDS = ("matching", "readability")  # D-17, D-18: one allowlist for both kinds
_PROPOSALS_NAME = "proposals.jsonl"
_VIEW_UNIT = re.compile(r"build/driver/(?:[^/]+/)+view/src/(ufo2p|tacp)/([a-z0-9_]+)\.c")
# F16: inline-asm tokens, matched case-sensitively on configure's blanked, spliced code.
_INLINE_ASM = re.compile(r"\b_{1,2}asm\b")
_PRAGMA_OPERATOR = re.compile(r"\b_Pragma\b")
# A `#pragma aux` directive; \s also takes the form feed and vertical tab the compiler skips.
_PRAGMA_AUX = re.compile(r"\s*#\s*pragma\s+aux(?![A-Za-z0-9_])(.*)", re.DOTALL)
_CODE_BODY = "="  # `#pragma aux name = <bytes>` emits code; `parm [eax]` and the like do not
# A `#pragma` directive of any kind (the matching layer during the pilot, M14), also spelled
# with the `%:` digraph for `#` (fix round 2 N6; configure's scanner does not translate it).
_PRAGMA = re.compile(r"\s*(#|%:)\s*pragma(?![A-Za-z0-9_])")

# D-17: the matching-session layer. The claim and the notes path come from the driver's env.
CLAIM_ENV = "REVERSEAPOC_CLAIM"
_CLAIM = re.compile(r"(ufo2p|tacp)/[a-z0-9_]+")
_READ_TOOLS = ("Read", "Glob", "Grep")
# 07.2-12 (D-10): "1" on a session whose arm sends the context pack to a non-Anthropic backend
# (backends.session_env sets it); such a session reads nothing under these directories.
EGRESS_ENV = "REVERSEAPOC_EGRESS"
_EGRESS_DENIED = ("orig", "third_party")
_WRITE_TOOLS = ("Edit", "Write", "MultiEdit")
_MATCHING_TOOLS = (*_READ_TOOLS, *_WRITE_TOOLS, "Bash")
_SYMBOLS = re.compile(r"config/[^/]+/symbols\.csv")  # D-19: shared naming state, driver-only
_SECRET_PREFIX = ".env"
# A character class could spell .env and is never judged, only refused (fix round 1 M2). Brace
# alternatives are expanded and each expansion judged (261109-gzw).
_GLOB_CLASSES = "[]"
_MAX_BRACE_EXPANSIONS = 64  # the most paths one Glob pattern or Grep glob may spell
_BRACE_GROUP = re.compile(r"(\{[^{}]*\})")  # one group with no brace inside it
# D-44: the attempt wrapper's argv forms, shared with the wrapper itself (06-15, ruling F27).
ATTEMPT_PREFIX = ("uv", "run", "--frozen", "reverseapoc", "attempt")
ATTEMPT_NAME_SLOT = "<NAME>"
ATTEMPT_FORMS = (
    ("check",),
    ("check", "--sweep"),
    ("asm",),
    ("asm", ATTEMPT_NAME_SLOT),
    ("context",),
)
# 07.2-02, 07.2-03 (D-26) and `attempt diff` (the latest check's full diff): the verbs only a
# matching session runs; a readability session gets no new form and keeps ATTEMPT_FORMS
# (forms_for).
MATCHING_FORMS = ATTEMPT_FORMS + (("giveup",), ("plan",), ("diff",))
# Review WR-04: the Bash tool's timeout an `attempt check` needs (a run lasts up to 580 s plus
# its clean-up); at the tool's 120 s default the wrapper is killed and check.lock stays behind.
CHECK_TIMEOUT_MS = 600_000
# The rule each source denial names: an #include problem is neither inline asm nor a #pragma.
_ALWAYS_ASM_RULE = "no inline asm in src/ or include/ (D-16, coding rules)"
_MATCHING_ASM_RULE = ("no inline asm and no #pragma of any kind during the pilot (D-18, M14; "
                      "flags and pragmas are owner-only)")  # fmt: skip
INCLUDE_RULE = "an #include names only a bare header name (CR-02, configure's D-12 rule)"
ATTEMPT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")  # a func_/D_ placeholder or a symbol name
_BASH_CHARS = re.compile(r"[A-Za-z0-9_ -]+")  # every character of every wrapper form, no more

_DRIVE = re.compile(r"[A-Za-z]:")
# Win32 file, Win32 device and NT object prefixes; after one, UNC\ names a share.
_NT_OBJECT = "\\??\\"
_DEVICE_PREFIXES = ("\\\\?\\", "\\\\.\\", _NT_OBJECT)
_UNC = "UNC\\"
_GIT_BASH_DRIVE = re.compile(r"\\([A-Za-z])(?=\\|$)")  # Git Bash's /c/..., slashes made \
PROJECT_ENV = "CLAUDE_PROJECT_DIR"
_HOOKS_REPO = Path(__file__).resolve().parents[2]  # tools/reverseapoc/hooks.py -> its checkout
_GIT = ".git"
_WORKTREE = re.compile(r"\.claude/worktrees/[^/]+/(.+)")


class HookError(ValueError):
    """A payload the hook cannot read; main turns it into exit 2 (a block)."""


@dataclass(frozen=True)
class Decision:
    deny: bool
    reason: str = ""


NO_OPINION = Decision(False)


def _deny(reason: str) -> Decision:
    return Decision(True, f"reverseapoc hooks: {reason}")


# Review WR-04: the denial of an `attempt check` whose Bash timeout is short; the driver's canary
# tells this refusal (the hook working) from a blocked wrapper by its exact reason.
CHECK_TIMEOUT_DENIAL = _deny("attempt check needs the Bash tool's timeout at its maximum, or the "
                             "tool kills the run and leaves check.lock behind: rerun it with "
                             f"`timeout: {CHECK_TIMEOUT_MS}`")  # fmt: skip


# --- paths -----------------------------------------------------------------------------------


def _is_windows(raw: str) -> bool:
    """Whether `raw` is a Windows form; on an NT host every path is one (fix round 1 C1)."""
    if os.name == "nt":
        return True
    return "\\" in raw or _DRIVE.match(raw) is not None or raw.startswith(("//?/", "//./"))


def _check_raw(raw: object) -> str:
    if not isinstance(raw, str) or not raw or "\0" in raw:
        raise HookError(f"path {raw!r} is not a usable path")
    return raw


def _undevice(text: str) -> str | None:
    """`text` (backslashes) without a Win32 or NT device prefix: `\\\\?\\C:\\x`, `\\\\.\\C:\\x`
    and `\\??\\C:\\x` become `C:\\x`, and `...\\UNC\\server\\share` becomes `\\\\server\\share`.
    None for a device form that names no drive or share (a volume GUID, GLOBALROOT, a pipe):
    only the host's realpath can map those."""
    for prefix in _DEVICE_PREFIXES:
        if not text.startswith(prefix):
            continue
        rest = text[len(prefix) :]
        if rest[: len(_UNC)].upper() == _UNC:
            return "\\\\" + rest[len(_UNC) :]
        drive, tail = ntpath.splitdrive(rest)
        return rest if _DRIVE.fullmatch(drive) and tail.startswith("\\") else None
    return text


def _windows_components(path: str) -> str:
    """`path` (normalised, backslashes) with each component as NTFS opens it: an alternate data
    stream suffix (`name:stream`) dropped and trailing dots and spaces stripped."""
    drive, rest = ntpath.splitdrive(path)
    parts = [part.split(":")[0].rstrip(". ") for part in rest.split("\\")]
    return drive + "\\".join(parts)


def _placed(path: str) -> bool:
    """Whether a backslashed path names a drive root or a share (`C:\\...`, `\\\\server\\share`)."""
    drive, rest = ntpath.splitdrive(path)
    return bool(drive) and (drive.startswith("\\\\") or rest.startswith("\\"))


def _windows_base(cwd: str) -> str | None:
    """The payload cwd as a drive-absolute Windows path, or None."""
    text = _undevice(cwd.replace("/", "\\")) if cwd else None
    return text if text is not None and _placed(text) else None


def _windows_joined(text: str, cwd: str) -> str:
    """`text` (backslashes, device prefixes kept) made absolute: a relative path joins the
    payload cwd, a rooted one with no drive (`\\Users\\...`) takes the cwd's drive (or the
    host's). A drive-relative path on another drive (`Q:x`) stays unplaced."""
    if text.startswith(("\\\\", _NT_OBJECT)) or ntpath.isabs(text):
        return text
    base = _windows_base(cwd)
    if text.startswith("\\"):
        return ntpath.join(base or os.getcwd(), text)
    if base is None:
        raise HookError(f"path {text!r} is relative and the payload has no usable cwd")
    return ntpath.join(base, text)


def _windows_lexical(joined: str) -> str | None:
    """The normalised, forward-slash form of an absolute Windows path; None for an unmappable
    device form. Raises HookError for a path that names no drive root or share."""
    path = _undevice(joined)
    if path is None:
        return None
    if not _placed(path):
        raise HookError(f"path {joined!r} cannot be placed on a drive or share")
    return ntpath.normpath(_windows_components(ntpath.normpath(path))).replace("\\", "/")


def _host_real(path: str) -> str | None:
    """The host's realpath of `path` (symlinks, 8.3 names, volume GUIDs, GLOBALROOT and `//./`
    resolved), forward slashes; None when the result names no drive or share. Raises
    HookError when the host cannot resolve it."""
    try:
        real = os.path.realpath(path)
    except (OSError, ValueError) as exc:
        raise HookError(f"path {path!r} cannot be resolved: {exc}") from None
    if os.name != "nt":
        return real
    plain = _undevice(real)
    return plain.replace("\\", "/") if plain is not None and _placed(plain) else None


def _windows_candidates(raw: str, cwd: str) -> list[str]:
    text = raw.replace("/", "\\")
    found = []
    forms = [text]
    bash_drive = _GIT_BASH_DRIVE.match(text)
    if bash_drive is not None:  # Git Bash's /c/... names C:\...
        forms.append(bash_drive.group(1) + ":\\" + text[bash_drive.end() :].lstrip("\\"))
    for form in forms:
        joined = _windows_joined(form, cwd)
        lexical = _windows_lexical(joined)
        if lexical is not None:
            found.append(lexical)
        # Python's realpath reads an NT object path (\??\...) as rooted on the current drive,
        # not as the object it names, so only its lexical form is resolved.
        raw_real = None if joined.startswith(_NT_OBJECT) else joined
        reals = [_host_real(s) for s in (raw_real, lexical) if s is not None and os.name == "nt"]
        if lexical is None and not any(reals):  # defence in depth: backs up the empty-result
            # raise in `candidates`, so a mutation of this one is equivalent (re-review m2)
            raise HookError(f"device path {raw!r} cannot be mapped to a drive or share")
        found.extend(real for real in reals if real is not None)
    return found


def _posix_candidates(raw: str, cwd: str) -> list[str]:
    if raw.startswith("/"):
        path = raw
    elif cwd:
        path = posixpath.join(cwd, raw)
    else:
        raise HookError(f"path {raw!r} is relative and the payload has no cwd")
    lexical = posixpath.normpath(path)
    return [lexical, _host_real(lexical) or lexical]


def candidates(raw: str, cwd: str = "") -> list[str]:
    """Every absolute, normalised form of `raw` with forward slashes (case kept): the lexical
    form and the host's real one (symlinks, 8.3 names, device paths resolved). A rule that
    denies any form denies the call. Raises HookError (exit 2) for a path that cannot be
    placed: a device path the host cannot map to a drive, or another drive's relative path."""
    raw = _check_raw(raw)
    cwd = cwd if isinstance(cwd, str) else ""
    windows = _is_windows(raw) or (not raw.startswith("/") and _is_windows(cwd))
    found = _windows_candidates(raw, cwd) if windows else _posix_candidates(raw, cwd)
    unique: dict[str, str] = {}
    for path in found:
        unique.setdefault(path.casefold(), path)
    if not unique:
        raise HookError(f"path {raw!r} cannot be placed")
    return list(unique.values())


def canonical(raw: str, cwd: str = "") -> str:
    """The first of `candidates`: the form the hook reads a file through."""
    return candidates(raw, cwd)[0]


def project_roots(env: Mapping[str, str]) -> tuple[str, ...]:
    """The forms of the project root: $CLAUDE_PROJECT_DIR, else the checkout holding hooks.py
    (fix round 1 C2). Every path is judged against it, wherever `.git` files sit."""
    raw = env.get(PROJECT_ENV) or str(_HOOKS_REPO)
    try:
        return tuple(candidates(raw))
    except HookError:
        return tuple(candidates(str(_HOOKS_REPO)))


def _relative(path: str, root: Path) -> str:
    return Path(path).relative_to(root).as_posix().casefold()


def _git_anchors(path: str) -> Iterator[str]:
    """`path` relative to EVERY ancestor holding `.git`, so a `.git` planted inside the checkout
    (config/.git, src/.git) cannot move the root (fix round 1 C2)."""
    if not Path(path).is_absolute():
        return
    for parent in Path(path).parents:
        if (parent / _GIT).exists():
            yield _relative(path, parent)


def _repo_forms(path: str, project: tuple[str, ...]) -> Iterator[str]:
    """The casefolded repo-relative forms of `path`: against the project root and against every
    ancestor holding `.git`, each also relative to a worktree under .claude/worktrees/<name>/
    (even one whose `.git` is missing), so a worktree's orig/ is still orig/."""
    inside = _inside(path, project)
    for rel in (*(() if inside is None else (inside,)), *_git_anchors(path)):
        yield rel
        inner = _WORKTREE.fullmatch(rel)
        if inner is not None:
            yield inner.group(1)


def _judged(paths: Sequence[str], project: tuple[str, ...]) -> Iterator[tuple[str, str]]:
    """(path, repo-relative form) for every form of every candidate path."""
    for path in paths:
        yield from ((path, rel) for rel in _repo_forms(path, project))


def _under(rel: str, directory: str) -> bool:
    return rel == directory or rel.startswith(directory + "/")


# --- the always-on layer (D-16, D-46) --------------------------------------------------------


def _is_notes(rel: str) -> bool:
    return rel.startswith(_NOTES_DIR + "/") and rel.rsplit("/", 1)[-1] == _NOTES_NAME


def _is_session_file(rel: str) -> bool:
    """One of SESSION_FILE_NAMES under build/driver/ (giveup.json, 07.2-02; plan.json and
    check-note.json, 07.2-03; D-26), the shape of the notes file's siblings."""
    return rel.startswith(_NOTES_DIR + "/") and rel.rsplit("/", 1)[-1] in SESSION_FILE_NAMES


def _is_proposals(rel: str) -> bool:
    return rel.startswith(_NOTES_DIR + "/") and rel.rsplit("/", 1)[-1] == _PROPOSALS_NAME


def _is_view_unit(rel: str, claim: str | None = None) -> bool:
    """Whether `rel` has the view-unit shape (D-24), for the claimed `<exe>/<unit>` if given."""
    view = _VIEW_UNIT.fullmatch(rel)
    return view is not None and (claim is None or f"{view.group(1)}/{view.group(2)}" == claim)


def _exempt(rel: str, *, notes: bool, session: bool) -> bool:
    """Whether `rel` under build/ is one of the driver's per-session files: the notes file
    (D-46) or its giveup.json, plan.json and check-note.json siblings (07.2-02, 07.2-03, D-26),
    or the view unit or proposals file (D-24), each at its shape only. The matching layer then
    decides who may write the siblings."""
    notes_file = notes and (_is_notes(rel) or _is_session_file(rel))
    return notes_file or (session and (_is_view_unit(rel) or _is_proposals(rel)))


def _protected(rel: str, *, notes: bool = False, session: bool = False) -> str | None:
    """Why the always layer refuses an edit of repo-relative `rel`, or None. `notes`: the path
    is the driver's REVERSEAPOC_ATTEMPT_NOTES or one of its SESSION_FILE_NAMES siblings (exempt
    only under build/driver/, D-46, D-26); `session`: it is one of `_session_paths` (exempt only
    at the view-unit or proposals shape, D-24)."""
    for directory, why in _PROTECTED_DIRS.items():
        if _under(rel, directory) and not _exempt(rel, notes=notes, session=session):
            return f"{directory}/ is protected for every session (D-16): {why}"
    if rel in _PROTECTED_FILES:
        return f"{rel} is protected for every session (D-16): {_PROTECTED_FILES[rel]}"
    if rel.endswith(_MANIFEST_SUFFIX):
        return f"{rel} is a hash manifest, protected for every session (D-16)"
    return None


def _cwd(payload: Mapping) -> str:
    cwd = payload.get("cwd")
    return cwd if isinstance(cwd, str) else ""


def _notes_paths(env: Mapping[str, str], cwd: str) -> frozenset[str]:
    """The casefolded forms of the driver's notes path and of its SESSION_FILE_NAMES siblings
    (07.2-02, 07.2-03), or none when it is unset or unusable."""
    raw = env.get(NOTES_ENV, "")
    try:
        paths = [path.casefold() for path in candidates(raw, cwd)] if raw else []
    except HookError:
        return frozenset()
    siblings = (posixpath.join(posixpath.dirname(path), name) for path in paths
                if posixpath.basename(path) == _NOTES_NAME
                for name in SESSION_FILE_NAMES)  # fmt: skip
    return frozenset((*paths, *siblings))


def _env_forms(
    env: Mapping[str, str], name: str, cwd: str, fits: Callable[[str], bool]
) -> frozenset[str]:
    """The casefolded forms of the path in env `name` when it lies under build/ and every
    repo-relative form of it there `fits`; none when it is unset, unusable or misshapen."""
    raw = env.get(name, "")
    try:
        paths = candidates(raw, cwd) if raw else []
    except HookError:
        return frozenset()
    rels = [rel for _path, rel in _judged(paths, project_roots(env)) if _under(rel, "build")]
    exact = bool(rels) and all(map(fits, rels))
    return frozenset(path.casefold() for path in paths) if exact else frozenset()


def _session_paths(env: Mapping[str, str], cwd: str) -> frozenset[str]:
    """The casefolded forms of the session's REVERSEAPOC_UNIT_FILE (only at the view shape
    `build/driver/.../view/src/<exe>/<unit>.c` naming the claim) and REVERSEAPOC_PROPOSALS
    (only proposals.jsonl under build/driver/), D-24 P6."""
    claim = _claim(env)
    unit = _env_forms(env, UNIT_FILE_ENV, cwd,
                      lambda rel: claim is not None and _is_view_unit(rel, claim))  # fmt: skip
    return unit | _env_forms(env, PROPOSALS_ENV, cwd, _is_proposals)


def _target(payload: Mapping) -> tuple[str, Mapping]:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, Mapping):
        raise HookError("the payload has no tool_input object")
    field = _PATH_FIELD[payload["tool_name"]]
    raw = tool_input.get(field)
    if not isinstance(raw, str):
        raise HookError(f"{payload['tool_name']} payload has no {field} string")
    return raw, tool_input


def _string(mapping: Mapping, key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise HookError(f"the edit has no {key} string")
    return value


def _read_current(path: str) -> str | None:
    """The file's text as the edit will see it, or None when it cannot be read."""
    try:
        return Path(path).read_bytes().decode("utf-8", "surrogateescape")
    except OSError:
        return None


def _apply(text: str | None, edit: Mapping) -> str | None:
    """`text` after one Edit (`old_string` -> `new_string`, once or with `replace_all`), or None
    when the edit cannot be placed verbatim (fix round 1 I2: no loose matching, CRLF or curly
    quotes, so the scanned text is the text the tool writes). An empty old_string places only
    on a file that does not exist yet (`text` None): the tool creates it from new_string."""
    old, new = _string(edit, "old_string"), _string(edit, "new_string")
    if not old:
        return new if text is None else None
    if text is None or old not in text:
        return None
    return text.replace(old, new, -1 if edit.get("replace_all") is True else 1)


def _post_edit_text(tool: str, tool_input: Mapping, path: str) -> str | None:
    """The file as the edit leaves it, or None when an edit cannot be placed verbatim."""
    if tool == "Write":
        return _string(tool_input, "content")
    edits = [tool_input] if tool == "Edit" else tool_input.get("edits")
    if not isinstance(edits, list) or not edits or not all(isinstance(e, Mapping) for e in edits):
        raise HookError(f"the {tool} payload has no list of edits")
    text = _read_current(path)
    for one in edits:
        text = _apply(text, one)
        if text is None:
            return None
    return text


def _configure():
    """configure.py, loaded through check's loader. Imported here, not at the top: it is the
    expensive part, and only edits in src/ and include/ need it."""
    from .check import _configure as load

    return load()


# 07-19 fix round 1 S1: after a directive's own `#`, a `#` or `##` operator (or its `%:` /
# `%:%:` digraph) could stringize or paste a banned token (`__a##sm`) past the token scan.
# Only the strict scan (any_pragma) refuses it: include/common.h's INCLUDE_ASM uses `##` (F16).
_DIRECTIVE_HASH = re.compile(r"\s*(?:#|%:)")
_HASH_OPERATOR = re.compile(r"#|%:")


# 07-19 fix round 2 S3: the keyword spellings of a pragma and of emitted bytes, refused by the
# strict scan like a #pragma directive.
_PRAGMA_KEYWORDS = re.compile(r"\b(?:__pragma|__emit)\b")


def _preprocessor_operator(logical: str) -> bool:
    lead = _DIRECTIVE_HASH.match(logical)
    return _HASH_OPERATOR.search(logical, lead.end() if lead else 0) is not None


def _inline_asm(logical: str, *, any_pragma_aux: bool, any_pragma: bool = False) -> str | None:
    found = _INLINE_ASM.search(logical) or _PRAGMA_OPERATOR.search(logical)
    if found is not None:
        return f"inline assembly `{found.group()}`"
    if any_pragma and _PRAGMA.match(logical):
        return "a #pragma directive"
    keyword = _PRAGMA_KEYWORDS.search(logical) if any_pragma else None
    if keyword is not None:
        return f"a pragma or emit keyword `{keyword.group()}`"
    if any_pragma and _preprocessor_operator(logical):
        return "a # or ## preprocessor operator (it could stringize or paste a banned token)"
    aux = _PRAGMA_AUX.match(logical)
    if aux is not None and (any_pragma_aux or _CODE_BODY in aux.group(1)):
        return "a #pragma aux" if any_pragma_aux else "a code-emitting #pragma aux (`=` body)"
    return None


def asm_problem(text: str, *, any_pragma_aux: bool = False, any_pragma: bool = False) -> str | None:
    """Why `text` (a src/ or include/ file) is refused, or None: inline asm (`_asm`, `__asm`,
    `_Pragma`) or a code-emitting `#pragma aux` (any `#pragma aux` with `any_pragma_aux`, D-18;
    any `#pragma` directive at all with `any_pragma`, M14) in its code, read through
    configure's D-12 scanner (translation phases 1-2, backslash continuations spliced, comments
    and literals blanked). Text the scanner cannot read as wcc386 does (a lone CR) is refused
    too."""
    cfg = _configure()
    try:
        code = cfg._NOT_CODE.sub(cfg._blank, text)
    except cfg._ConditionalError as exc:
        return f"the text cannot be read as wcc386 reads it: {exc}"
    for first, _last, logical in cfg._logical_lines(code.split("\n")):
        found = _inline_asm(logical, any_pragma_aux=any_pragma_aux, any_pragma=any_pragma)
        if found is not None:
            return f"line {first + 1} (logical line start): {found}"
    return None


def include_problem(text: str) -> str | None:
    """Why `text` (a src/ or include/ file) is refused for an #include of anything but a bare
    header name: "name.h" from include/, or <name.h> from include/ or the compiler's own headers
    (Watcom's H directory, which game code may need for conio.h or i86.h). None when it is not
    (06-REVIEW CR-02: configure's D-12 rule, so no unscanned file such as notes.md reaches the
    compile)."""
    cfg = _configure()
    try:
        includes = cfg.include_problems(text)
    except cfg._ConditionalError as exc:
        return f"the text cannot be read as wcc386 reads it: {exc}"
    return includes[0] if includes else None


def _source_problem(
    tool: str, tool_input: Mapping, path: str, *, asm_rule: str, any_pragma_aux: bool,
    any_pragma: bool = False,
) -> str:  # fmt: skip
    """The deny reason for an edit in src/ or include/, or '': an inline-asm or pragma problem
    under `asm_rule`, an #include problem under INCLUDE_RULE."""
    if tool == "NotebookEdit":
        return f"{asm_rule}: a notebook edit in src/ or include/ cannot be scanned for inline asm"
    text = _post_edit_text(tool, tool_input, path)
    if text is None:
        return f"{asm_rule}: an edit whose old_string is not in the file verbatim cannot be checked"
    problem = asm_problem(text, any_pragma_aux=any_pragma_aux, any_pragma=any_pragma)
    if problem:
        return f"{asm_rule}: {problem}"
    include = include_problem(text)
    return f"{INCLUDE_RULE}: {include}" if include else ""


def _always(payload: Mapping, env: Mapping[str, str]) -> Decision:
    tool = payload.get("tool_name")
    if tool in SHELL_TOOLS:
        decision = _worktree_command(payload)
        return decision if decision.deny else _drive_command(payload, env)
    if tool not in EDIT_TOOLS:
        return NO_OPINION
    raw, tool_input = _target(payload)
    cwd = _cwd(payload)
    notes = _notes_paths(env, cwd)
    session = _session_paths(env, cwd)
    paths = candidates(raw, cwd)
    scanned = False
    for path, rel in _judged(paths, project_roots(env)):
        own = path.casefold() in session
        reason = _protected(rel, notes=path.casefold() in notes, session=own)
        if reason is not None:
            return _deny(reason)
        # P6: the view unit is a src/ file under build/, so it is scanned like src/
        view = own and _is_view_unit(rel)
        scanned = scanned or view or any(_under(rel, d) for d in _SCANNED_DIRS)
    problem = _source_problem(tool, tool_input, paths[0], asm_rule=_ALWAYS_ASM_RULE,
                              any_pragma_aux=False) if scanned else ""  # fmt: skip
    return _deny(problem) if problem else _drive_edit(tool, raw, paths, env)


def decide(
    payload: Mapping,
    *,
    layer: str,
    env: Mapping[str, str],
    tracked: Callable[[str], bool],
) -> Decision:
    """The hook's decision on one PreToolUse payload. `env` carries the driver's variables;
    `tracked(rel)` says whether a repo-relative path is tracked by git. Raises HookError for a
    payload it cannot read (main blocks it)."""
    if not isinstance(payload, Mapping):
        raise HookError("the payload is not a JSON object")
    if layer == LAYER_ALWAYS:
        return _always(payload, env)
    if layer == LAYER_MATCHING:
        return _matching(payload, env, tracked)
    raise HookError(f"unknown layer {layer!r}")


# --- the worktree command rule (261109-gzy) --------------------------------------------------

# A harness worktree's cwd: <main>/.claude/worktrees/<name>, or a directory below it.
_WORKTREE_CWD = re.compile(r"(.*?)/\.claude/worktrees/([^/]+)(?:/|$)", re.IGNORECASE)
_WORKTREES = "/.claude/worktrees/"
_SLASHES = re.compile(r"/+")
_SIBLING_CHAR = re.compile(r"[a-z0-9_-]")  # after the main path: a sibling such as <main>-old
_NAME_CHAR = re.compile(r"[a-z0-9_.-]")  # after the own worktree: another (<name>2, <name>.bak)
_RELATIVE_HINT = (
    "the main checkout is read-only for worktree agents: spell it relative to the worktree "
    "root, as in REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom"
)
# Words that name a script: the text after a word's last `=` (an assignment, --opt=) ends so.
_SCRIPT_SUFFIX = re.compile(r"\.(?:py|sh|bash|js|mjs|cjs|ps1)$", re.IGNORECASE)
_PYTHON_SUFFIX = re.compile(r"\.py$", re.IGNORECASE)
# What a shell would expand in a script word, so the hook cannot read it as written: a variable
# ($, $env:, %VAR%), a command substitution or PowerShell escape (`), a glob, a brace, a
# backslash-newline continuation, a leading ~.
_EXPANSION = re.compile(r"[$`%*?\[{]|\\\n|^~")
# Ruling 2, as 261112-fdw leaves it (A4): a command that names a script (anywhere in its text)
# and holds a heredoc or here-string marker or a backslash-newline continuation is denied, since
# the hook cannot tell which file runs. Both are operators, so a raw match can only over-deny;
# directory changes, inline code and eval are refused by the allowlist instead.
_SCRIPT_MENTION = re.compile(r"\.(?:py|sh|bash|js|mjs|cjs|ps1)(?![A-Za-z0-9_])", re.IGNORECASE)
_INDIRECTION = re.compile(r"<<|\\\r?\n")
_SCRIPT_CAP = 1 << 20  # 1 MiB, more than three times the largest tracked tool (driver.py, ~300 KB)
# UTF-32 first: its little-endian BOM (FF FE 00 00) starts with UTF-16's.
_UTF32_BOMS = (codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)
_UTF16_BOMS = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)
_UNSCANNABLE_CHARS = ("\0", "\ufeff")  # a NUL, or a byte-order mark left inside the text
# Bash: a here-document body is data, not words (an apostrophe in it must not break the split).
_HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\1([^\n]*\n).*?^[ \t]*\2[ \t]*$",
                      re.MULTILINE | re.DOTALL)  # fmt: skip
_BASH_OPERATORS = ";&|()<>\n"
# PowerShell: an operator (a redirection or a separator), else a word of quoted runs, backtick
# escapes (an escaped space stays in the word) and plain characters.
_POWERSHELL_TOKEN = re.compile(
    r"""(?P<op>[0-9*]?>>?(?:&[0-9])?|<|[;|&(){}\n]+)"""
    r"""|(?P<word>(?:'[^']*'|"(?:`.|[^"`])*"|`.|[^\s'";|&<>(){}`])+)"""
)
_QUOTES = re.compile(r"['\"]")
# 261112-fdw A2: PowerShell takes U+2018-U+201B for ' and U+201C-U+201E for ".
_POWERSHELL_QUOTES = str.maketrans({**dict.fromkeys("\u2018\u2019\u201a\u201b", "'"),
                                    **dict.fromkeys("\u201c\u201d\u201e", '"')})  # fmt: skip
# A PowerShell word in runs: a single-quoted run is literal; a double-quoted run and bare text
# decode backtick escapes (`u{HEX} up to U+10FFFF, else only the backtick is dropped; `X is X).
_POWERSHELL_RUN = re.compile(
    r"""'(?P<single>[^']*)'|"(?P<double>(?:`.|[^"`])*)"|(?P<bare>(?:`.|[^'"`])+|.)""", re.DOTALL
)
_BACKTICK_ESCAPE = re.compile(r"`(?:u\{([0-9A-Fa-f]{1,6})\}|(.))", re.DOTALL)
_MAX_CODE_POINT = 0x10FFFF
_HERE_STRING = re.compile(r"@(['\"])[ \t]*\r?\n")  # a PowerShell here-string opens
# Commands that write the files they name; every word of such a command counts as written.
_WRITERS = frozenset({
    "tee", "cp", "mv", "install", "ln", "touch", "dd", "curl", "wget",
    "out-file", "set-content", "add-content", "new-item", "copy-item", "move-item", "tee-object",
    "invoke-webrequest", "ni", "sc", "ac", "copy", "move", "cpi", "mi", "iwr",
})  # fmt: skip
# 261112-fdw: the shapes every simple command of a script-naming worktree call must have (A6).
_RUNNERS = frozenset({"bash", "node", "python"})  # a plain interpreter, then a plain script path
_UV_FLAGS = frozenset({"--frozen"})
_UV_PROGRAMS = frozenset({"pytest", "reverseapoc", "ruff"})  # `uv run python` is a runner
_GIT_FREE = frozenset({
    "add", "cat-file", "check-ignore", "checkout", "commit", "diff", "log", "ls-files", "merge",
    "merge-base", "mv", "restore", "rev-list", "rev-parse", "rm", "show", "show-ref", "status",
})  # fmt: skip
# Options that write a file or run a program (coordinator amendment 2), refused in every
# abbreviation git accepts; `--no-ext-diff` and `--no-textconv` pass.
_GIT_REFUSED = ("--output", "--ext-diff", "--textconv")
_GIT_BRANCH_FLAGS = frozenset({"--show-current", "--list", "-l", "-a", "--all", "-r", "--remotes",
                               "-v", "-vv", "--verbose"})  # fmt: skip
_GIT_BRANCH_LIST = frozenset({"--list", "-l"})  # patterns may follow these, never a new name
_GIT_LISTINGS = frozenset({"worktree", "stash"})  # only as `git <sub> list`
# Commands that read, copy, compare or print and run nothing.
_DATA_VERBS = frozenset({
    "[", "cat", "cp", "diff", "echo", "grep", "head", "ls", "mkdir", "tail", "tee", "test", "true",
    "wc", "get-content", "select-object", "select-string",
})  # fmt: skip
_FIND_REFUSED = frozenset({"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fls", "-fprint",
                           "-fprint0", "-fprintf"})  # fmt: skip
_SED_ADDRESS = r"(?:\d+|\$)(?:,(?:\d+|\$))?p"  # N, N,M or $ addresses, each printed
_SED_PRINT = re.compile(rf"{_SED_ADDRESS}(?:;{_SED_ADDRESS})*")
# Variables that steer which program a listed command runs, or the code or configuration it
# loads (compared uppercased, as Windows does); setting one is refused (A6 b).
_STEERING_NAMES = frozenset({
    "PATH", "PATHEXT", "HOME", "USERPROFILE", "XDG_CONFIG_HOME", "IFS", "CDPATH", "ENV", "SHELL",
    "COMSPEC", "EDITOR", "VISUAL", "PAGER", "SHELLOPTS", "BASHOPTS", "PS4",
})  # fmt: skip
_STEERING_PREFIXES = ("BASH_", "DYLD_", "GIT_", "LD_", "NODE_", "PYTEST_", "PYTHON", "UV_")
_BASH_ASSIGNMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=")
_POWERSHELL_ASSIGNMENT = re.compile(r"\$env:REVERSEAPOC_[A-Za-z0-9_]+ *= *'[^']*'", re.IGNORECASE)
_BASH_REDIRECTIONS = frozenset({"<", ">", ">>", ">&", "&>", "&>>", "<&", ">|", "<>"})


def _worktree_pairs(cwd: str) -> list[tuple[str, str]]:
    """(main checkout, worktree name), case kept, for every form of `cwd` that is a harness
    worktree or lies below one; empty outside a worktree."""
    pairs = []
    for form in candidates(cwd):
        found = _WORKTREE_CWD.match(form)
        if found is not None:
            pairs.append((found.group(1), found.group(2)))
    return pairs


def _normalised(text: str) -> str:
    """`text` casefolded, every backslash a `/`, each run of `/` one `/`."""
    return _SLASHES.sub("/", text.casefold().replace("\\", "/"))


def _needle(main: str) -> str:
    """The main checkout's path without its drive letter, so every drive and device prefix
    spelling (`C:`, `/c`, `//./C:`, a rooted `\\Users`) holds it."""
    return _normalised(main[2:] if _DRIVE.match(main) else main)


def _follows(text: str, index: int, char: re.Pattern[str]) -> bool:
    return index < len(text) and char.match(text, index) is not None


def _hit(text: str, needle: str, own: str) -> bool:
    """Whether normalised `text` holds `needle` not followed by a sibling's name character, nor
    by this session's own worktree `own` (`/.claude/worktrees/<name>`, casefolded) as a whole
    component."""
    start = text.find(needle)
    while start >= 0:
        end = start + len(needle)
        mine = text.startswith(own, end) and not _follows(text, end + len(own), _NAME_CHAR)
        if not mine and not _follows(text, end, _SIBLING_CHAR):
            return True
        start = text.find(needle, start + 1)
    return False


def _spells_main(text: str, pairs: Sequence[tuple[str, str]]) -> bool:
    folded = _normalised(text)
    return any(_hit(folded, _needle(main), _WORKTREES + name.casefold()) for main, name in pairs)


def _spells(main: str) -> str:
    return f"spells the main checkout's absolute path {main} (261109-gzy); {_RELATIVE_HINT}"


def _heredocs_dropped(command: str) -> str:
    return _HEREDOC.sub(r"<<\1\2\1\3", command)


def _bash_tokens(command: str) -> list[tuple[str, bool]]:
    """(token, is an operator) as Bash splits the command: quotes removed, escapes resolved,
    here-document bodies dropped. A command it cannot split blocks (exit 2)."""
    lexer = shlex.shlex(_heredocs_dropped(command), posix=True,
                        punctuation_chars=_BASH_OPERATORS)  # fmt: skip
    lexer.whitespace = " \t\r"  # a newline separates commands, like `;`
    lexer.whitespace_split = True
    lexer.commenters = ""  # ruling 2: no `#` comment hides a word from the split
    try:
        texts = list(lexer)
    except ValueError as exc:
        raise HookError(f"the Bash command cannot be split as the shell splits it: {exc}") from None
    return [(text, bool(text) and all(c in _BASH_OPERATORS for c in text)) for text in texts]


def _powershell_tokens(command: str) -> list[tuple[str, bool]]:
    """(token, is an operator) for a PowerShell command, each word as written (_reading strips
    its quotes)."""
    tokens = []
    for found in _POWERSHELL_TOKEN.finditer(command):
        op = found.group("op")
        tokens.append((op, True) if op is not None else (found.group(), False))
    return tokens


def _reading(tool: str, text: str) -> str:
    """The form of a word the hook reads a script by: a Bash token as shlex gave it, a
    PowerShell word with its quotes removed (a word that needed them for `$` or a backtick
    escape is caught by _EXPANSION)."""
    return _QUOTES.sub("", text) if tool == "PowerShell" else text


def _redirection(op: str) -> bool:
    return "<" in op or ">" in op


def _command_name(word: str) -> str:
    return posixpath.basename(word.replace("\\", "/")).casefold().removesuffix(".exe")


def _escaped(found: re.Match[str]) -> str:
    code = found.group(1)
    if code is None:
        return found.group(2)
    value = int(code, 16)
    return chr(value) if value <= _MAX_CODE_POINT else found.group()[1:]


def _powershell_run(found: re.Match[str]) -> str:
    single = found.group("single")
    if single is not None:
        return single
    double = found.group("double")
    return _BACKTICK_ESCAPE.sub(_escaped, double if double is not None else found.group("bare"))


def _plain(tool: str, text: str) -> str:
    """The detection form of a word, what the shell runs it as (A2): a Bash token as it is, a
    PowerShell word with its quotes removed and its backtick escapes decoded outside
    single-quoted runs. Decoding a special letter (`n) to the letter can only over-detect."""
    if tool != "PowerShell":
        return text
    return "".join(_powershell_run(found) for found in _POWERSHELL_RUN.finditer(text))


def _segment_words(tool: str, segment: Sequence[tuple[str, bool]]) -> Iterator[tuple[str, bool]]:
    """(raw word, written) for the words of one simple command: written after an output
    redirection, or every word when the command is one of _WRITERS."""
    verb = next((text for text, op in segment if not op and "=" not in text), "")
    writer = _command_name(_plain(tool, verb)) in _WRITERS
    for index, (text, op) in enumerate(segment):
        if op:
            continue
        before, before_op = segment[index - 1] if index else ("", False)
        yield text, writer or (before_op and ">" in before)


def _segment_scripts(tool: str, segment: Sequence[tuple[str, bool]]) -> Iterator[tuple[str, bool]]:
    """(reading tail, written) for each word of one simple command whose detection form, after
    its last `=`, ends with a script suffix. The reader gets the reading form, so a word that
    needs a backtick to show its suffix reaches _EXPANSION."""
    for text, written in _segment_words(tool, segment):
        if _SCRIPT_SUFFIX.search(_plain(tool, text).rsplit("=", 1)[-1]):
            yield _reading(tool, text).rsplit("=", 1)[-1], written


def _simple_commands(tool: str, command: str) -> list[list[tuple[str, bool]]]:
    """The command's simple commands, each a list of (raw token, is an operator), split at
    every separator (a redirection stays in its command). A Bash command shlex cannot split
    blocks (exit 2)."""
    return [segment for segment, _separator in _separated(tool, command)]


def _separated(tool: str, command: str) -> list[tuple[list[tuple[str, bool]], str]]:
    """`_simple_commands`, each with the separator operator after it as the splitter gave it
    (a run such as `);` or `&&\\n` stays one operator; '' after the last)."""
    tokens = _bash_tokens(command) if tool == "Bash" else _powershell_tokens(command)
    commands, segment = [], []
    for text, op in [*tokens, ("", True)]:
        if op and not _redirection(text):
            commands.append((segment, text))
            segment = []
            continue
        segment.append((text, op))
    return commands


def _unterminated(tool: str) -> HookError:
    return HookError(f"the {tool} command holds an unterminated command substitution, so the "
                     "hook cannot judge it (261112-fdw)")  # fmt: skip


def _quote_end(text: str, index: int) -> int:
    """The index of the `'` closing the single-quoted run opened at `index` (the last index when
    none does: the shell refuses that command, and an open substitution still raises)."""
    end = text.find("'", index + 1)
    return len(text) - 1 if end < 0 else end


def _backtick_end(tool: str, text: str, index: int) -> int:
    """The index of the next unescaped backtick: the end of a Bash backtick substitution."""
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == "`":
            return index
        index += 1
    raise _unterminated(tool)


def _bash_walk(tool: str, text: str, index: int, *, closing: bool) -> tuple[list[str], int]:
    """Walk Bash text from `index`: the contents of the substitutions found at this level, and,
    when `closing`, the index of the `)` that closes the substitution the walk started in.
    Outside single quotes a backslash escapes the next character, and `$(` and a backtick open a
    substitution; parentheses count outside quotes."""
    found, depth, quoted = [], 1, False
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        opener = 2 if text.startswith("$(", index) else int(char == "`")
        if opener:
            end = (_bash_walk(tool, text, index + 2, closing=True)[1] if opener == 2
                   else _backtick_end(tool, text, index + 1))  # fmt: skip
            found.append(text[index + opener : end])
            index = end + 1
            continue
        if char == "'" and not quoted:
            index = _quote_end(text, index) + 1
            continue
        if char == '"':
            quoted = not quoted
        elif closing and not quoted and char in "()":
            depth += 1 if char == "(" else -1
            if depth == 0:
                return found, index
        index += 1
    if closing:
        raise _unterminated(tool)
    return found, index


def _powershell_walk(tool: str, text: str, index: int, *, closing: bool) -> tuple[list[str], int]:
    """_bash_walk for PowerShell: `$(` opens a subexpression in bare text, in double-quoted runs
    and in double-quoted here-strings; a backtick escapes the next character; single-quoted runs
    and here-strings are literal; parentheses count in bare text."""
    found, depth, mode = [], 1, ""  # mode: "" bare, '"' a double-quoted run, "@" a here-string
    while index < len(text):
        char = text[index]
        here = _HERE_STRING.match(text, index) if mode == "" else None
        if char == "`":
            index += 2
        elif text.startswith("$(", index):
            end = _powershell_walk(tool, text, index + 2, closing=True)[1]
            found.append(text[index + 2 : end])
            index = end + 1
        elif here is not None and here.group(1) == "'":
            end = text.find("\n'@", here.end() - 1)
            index = len(text) if end < 0 else end + 3
        elif here is not None:
            mode, index = "@", here.end() - 1  # at its newline, so an empty one closes too
        elif mode == "@" and text.startswith('\n"@', index):
            mode, index = "", index + 3
        elif mode == "" and char == "'":
            index = _quote_end(text, index) + 1
        elif char == '"' and mode != "@":
            mode, index = ("" if mode else '"'), index + 1
        elif closing and mode == "" and char in "()":
            depth += 1 if char == "(" else -1
            if depth == 0:
                return found, index
            index += 1
        else:
            index += 1
    if closing:
        raise _unterminated(tool)
    return found, index


def _substitutions(tool: str, command: str) -> list[str]:
    """A10: the contents of every command substitution the command holds, nested ones included
    (each content is scanned again). An unterminated one blocks (exit 2)."""
    walk = _bash_walk if tool == "Bash" else _powershell_walk
    pending = walk(tool, _heredocs_dropped(command) if tool == "Bash" else command, 0,
                   closing=False)[0]  # fmt: skip
    found = []
    while pending:
        content = pending.pop()
        found.append(content)
        pending.extend(walk(tool, content, 0, closing=False)[0])
    return found


def _script_words(tool: str, command: str) -> list[tuple[str, bool]]:
    """(script word, written) for every word of the command that names a script."""
    words = []
    for segment in _simple_commands(tool, command):
        words.extend(_segment_scripts(tool, segment))
    return words


def _script_bytes(path: str) -> bytes | None:
    """The first _SCRIPT_CAP + 1 bytes of the file at placed `path`, or None when it is not a
    regular file."""
    if not Path(path).is_file():
        return None
    with Path(path).open("rb") as handle:
        return handle.read(_SCRIPT_CAP + 1)


def _script_text(data: bytes, path: str) -> str:
    """A script's text as its interpreter reads it: a .py file strictly in the encoding Python
    detects (its BOM or coding cookie; SyntaxError when it finds none it can use), else strict
    UTF-32 or UTF-16 after their BOM, else UTF-8 (a UTF-8 BOM dropped) with surrogateescape."""
    if _PYTHON_SUFFIX.search(path):
        return data.decode(tokenize.detect_encoding(io.BytesIO(data).readline)[0])
    if data.startswith(_UTF32_BOMS):
        return data.decode("utf-32")
    if data.startswith(_UTF16_BOMS):
        return data.decode("utf-16")
    return data.decode("utf-8-sig", "surrogateescape")


def _where(word: str, tool: str, pairs: Sequence[tuple[str, str]]) -> str:
    return f"the script {word} that a {tool} command from the harness worktree {pairs[0][1]} runs"


def _unscannable(where: str, why: str) -> str:
    return f"{where} {why}, so it cannot be scanned for the main checkout's path (261109-gzy)"


def _script_denial(word: str, path: str, tool: str, pairs: Sequence[tuple[str, str]]) -> str:
    """Why the script at placed `path` (named `word`) is refused, or '': over _SCRIPT_CAP, not
    one text (no Python source encoding, a NUL, an inner BOM), or its text spells the main
    checkout's absolute path."""
    where = _where(word, tool, pairs)
    try:
        data = _script_bytes(path)
        over = data is not None and len(data) > _SCRIPT_CAP
        text = "" if data is None or over else _script_text(data, path)
    except SyntaxError as exc:
        return _unscannable(where, f"has no source encoding Python can use ({exc})")
    except (OSError, UnicodeDecodeError) as exc:
        raise HookError(f"script {word!r} cannot be read: {exc}") from None
    if over:
        return _unscannable(where, f"is over {_SCRIPT_CAP} bytes")
    if any(char in text for char in _UNSCANNABLE_CHARS):
        return _unscannable(where, "holds a NUL or an inner byte-order mark (it is not one text)")
    return f"{where} {_spells(pairs[0][0])}" if _spells_main(text, pairs) else ""


def _scripts_denial(
    words: Sequence[tuple[str, bool]], cwd: str, tool: str, pairs: Sequence[tuple[str, str]]
) -> str:
    """Why a script word of the command is refused, or '': it needs shell expansion, the command
    also writes it and names it again (it would run unscanned), or _script_denial refuses it.
    Each word is placed as written; a placing failure blocks (exit 2)."""
    for word, _written in words:
        if _EXPANSION.search(word):
            return (f"{_where(word, tool, pairs)} needs shell expansion ($, %, a backtick, a glob "
                    "or a leading ~), so it cannot be read as written (261109-gzy); name it by a "
                    "literal path")  # fmt: skip
    placed = [(word, canonical(word, cwd), written) for word, written in words]
    mentions = Counter(path.casefold() for _word, path, _written in placed)
    rewritten = {path.casefold() for _word, path, written in placed if written}
    first: dict[str, tuple[str, str]] = {}
    for word, path, _written in placed:
        first.setdefault(path.casefold(), (word, path))
    for key, (word, path) in first.items():
        if key in rewritten and mentions[key] > 1:
            return (f"{_where(word, tool, pairs)} and the same command writes it, so it "
                    "would run unscanned (261109-gzy); write it in one call, run it in the "
                    "next")  # fmt: skip
        reason = _script_denial(word, path, tool, pairs)
        if reason:
            return reason
    return ""


# --- 261112-fdw: the allowlist of simple-command shapes (A5-A7) ---


def _plain_script(word: str) -> bool:
    """A7: a word that ends with a script suffix, holds no `=` and is no option."""
    return bool(_SCRIPT_SUFFIX.search(word)) and "=" not in word and not word.startswith("-")


def _qualified(word: str) -> bool:
    return "/" in word or "\\" in word


def _direct_run(word: str) -> bool:
    """A6 d: a verb that is a plain script path (a bare name is looked up in PATH, not here)."""
    return _plain_script(word) and _qualified(word)


def _verb(word: str) -> str:
    """A bare program name, casefolded with `.exe` dropped; '' for a path (only a direct run may
    be one, so `./git` is not git)."""
    return "" if _qualified(word) else word.casefold().removesuffix(".exe")


def _steering(name: str) -> bool:
    upper = name.upper()
    return upper in _STEERING_NAMES or upper.startswith(_STEERING_PREFIXES)


def _first(words: Sequence[str], refused: Callable[[str], bool]) -> str:
    return next((word for word in words if refused(word)), "")


def _shape(tool: str, segment: Sequence[tuple[str, bool]]) -> tuple[list[str], str]:
    """A5: the raw words of one simple command with each redirection and its target removed (a
    PowerShell `N>&M` takes none), and the operator that leaves it unreadable, or '': a Bash
    process substitution or other unknown redirection, or one with no target."""
    words, target = [], False
    for text, op in segment:
        if not op:
            if not target:
                words.append(text)
            target = False
            continue
        if target or (tool == "Bash" and text not in _BASH_REDIRECTIONS):
            return words, text
        target = tool == "Bash" or not text[-1].isdigit()
    return (words, segment[-1][0]) if target else (words, "")


def _assignments(words: Sequence[str]) -> tuple[int, str]:
    """A6 b: how many leading Bash words are NAME=value assignments, and the first one that sets
    a steering variable ('' when none does)."""
    for index, word in enumerate(words):
        found = _BASH_ASSIGNMENT.match(word)
        if found is None:
            return index, ""
        if _steering(found.group(1)):
            return index, word
    return len(words), ""


def _runner_offender(verb: str, rest: Sequence[str], cwd: str) -> str:
    """A6 e: '' when `rest` starts with a plain script path, else the offending word. For bash a
    bare name must be a file in the cwd, since bash searches PATH for one it cannot find."""
    if not rest or not _plain_script(rest[0]):
        return rest[0] if rest else verb
    if verb == "bash" and not _qualified(rest[0]) and not Path(canonical(rest[0], cwd)).is_file():
        return rest[0]
    return ""


def _uv_offender(rest: Sequence[str], cwd: str) -> str:
    """A6 f: `uv run`, any `--frozen`, then python and a plain script path, or a listed program."""
    if rest[:1] != ["run"]:
        return rest[0] if rest else "uv"
    index = 1
    while index < len(rest) and rest[index] in _UV_FLAGS:
        index += 1
    words = rest[index:]
    if not words:
        return "run"
    program = _verb(words[0])
    if program == "python":
        return _runner_offender(program, words[1:], cwd)
    return "" if program in _UV_PROGRAMS else words[0]


def _git_refused(word: str) -> bool:
    """An option of _GIT_REFUSED, or an abbreviation of one (`--outp`, `--ext`)."""
    option = word.split("=", 1)[0]
    if len(option) <= len("--") or not option.startswith("--"):
        return False
    return any(name.startswith(option) or option.startswith(name) for name in _GIT_REFUSED)


def _git_grep_refused(word: str) -> bool:
    """`git grep -O` (also inside a bundle of short options) and `--op...` run a pager program."""
    bundle = word.startswith("-") and not word.startswith("--") and "O" in word
    return bundle or word.startswith("--op") or _git_refused(word)


def _git_branch_offender(args: Sequence[str]) -> str:
    """Only listing: the listed flags, and patterns after --list or -l (a bare name creates)."""
    listing = False
    for word in args:
        if word in _GIT_BRANCH_FLAGS:
            listing = listing or word in _GIT_BRANCH_LIST
            continue
        if not listing or word.startswith("-"):
            return word
    return ""


def _git_offender(rest: Sequence[str]) -> str:
    """A6 g: a listed subcommand right after `git` (a global option before it is refused)."""
    if not rest:
        return "git"
    sub, args = rest[0], rest[1:]
    if sub in _GIT_FREE:
        return _first(args, _git_refused)
    return _git_listing_offender(sub, args)


def _git_listing_offender(sub: str, args: Sequence[str]) -> str:
    """The git subcommands both git rules (A6 g and the drive guard) list beside their own:
    grep, a branch listing and `git <worktree|stash> list`; '' or the offending word."""
    if sub == "grep":
        return _first(args, _git_grep_refused)
    if sub == "branch":
        return _git_branch_offender(args)
    if sub in _GIT_LISTINGS and args[:1] == ["list"]:
        return _first(args[1:], _git_refused)
    return sub


def _find_offender(args: Sequence[str]) -> str:
    return _first(args, _FIND_REFUSED.__contains__)


def _sort_offender(args: Sequence[str]) -> str:
    """Any long option: `--compress-program` runs a program, and GNU takes it abbreviated."""
    return _first(args, lambda word: word.startswith("--"))


def _sed_offender(args: Sequence[str]) -> str:
    """Only `sed -n <line-number prints> <files>`, with no option after the script."""
    if args[:1] != ["-n"]:
        return args[0] if args else "sed"
    if len(args) < 2 or not _SED_PRINT.fullmatch(args[1]):
        return args[1] if len(args) > 1 else "-n"
    return _first(args[2:], lambda word: word.startswith("-"))


_DATA_CHECKS = {"find": _find_offender, "sed": _sed_offender, "sort": _sort_offender}


def _shape_offender(words: Sequence[str], cwd: str) -> str:
    """A6 d-h on a command's detection-form words, assignments removed: '' or the offender."""
    head, rest = words[0], words[1:]
    if _direct_run(head):
        return ""
    verb = _verb(head)
    if verb in _RUNNERS:
        return _runner_offender(verb, rest, cwd)
    if verb == "uv":
        return _uv_offender(rest, cwd)
    if verb == "git":
        return _git_offender(rest)
    if verb in _DATA_CHECKS:
        return _DATA_CHECKS[verb](rest)
    return "" if verb in _DATA_VERBS else head


def _command_offender(tool: str, raw: Sequence[str], cwd: str) -> str:
    """The word that puts one simple command (its raw words, redirections removed) outside the
    allowlist (A6), or '' when it fits."""
    if tool == "PowerShell" and _POWERSHELL_ASSIGNMENT.fullmatch(" ".join(raw)):
        return ""  # c: $env:REVERSEAPOC_<NAME> = '<literal>'
    words = [_plain(tool, word) for word in raw]
    if tool == "Bash":
        words = words[1:] if words[:1] == ["!"] else words
        count, steering = _assignments(words)
        if steering:
            return steering
        words = words[count:]
    return _shape_offender(words, cwd) if words else ""


def _unlisted(tool: str, name: str, word: str) -> str:
    return (f"a {tool} command from the harness worktree {name} names a script and holds "
            f"{word!r}, which is not a plain interpreter followed by a plain script path nor a "
            "listed command (261112-fdw), so the hook cannot tell which file runs (261109-gzy); "
            "run the script as `uv run python <path>`, `bash <path>`, `node <path>` or "
            "`& <path>` from the worktree root, in a call of its own")  # fmt: skip


def _runspace(name: str, word: str) -> str:
    return (f"a PowerShell command from the harness worktree {name} runs the script {word!r} in "
            "this shell, where it can move the location every later command runs in, so the "
            "hook cannot tell which file runs (261109-gzy, 261112-fdw); run each script in a "
            "call of its own")  # fmt: skip


def _allowlist_denial(tool: str, command: str, cwd: str, name: str, *, nested: bool = False) -> str:
    """Why a simple command of a script-naming call (or of a substitution in it, `nested`) has no
    listed shape (A5, A6), or why it names a script or holds a `$(` after a PowerShell direct
    script run, or runs one inside a subexpression (A8: the script runs in the caller's
    runspace); else ''."""
    direct = ""
    for segment in _simple_commands(tool, command):
        later = any(_segment_scripts(tool, segment)) or any("$(" in text for text, _op in segment)
        if direct and later:
            return _runspace(name, direct)
        raw, bad = _shape(tool, segment)
        offender = bad or _command_offender(tool, raw, cwd)
        if offender:
            return _unlisted(tool, name, offender)
        if tool != "PowerShell" or not raw or not _direct_run(_plain(tool, raw[0])):
            continue
        if nested:
            return _runspace(name, raw[0])
        direct = direct or raw[0]
    return ""


def _indirect(tool: str, name: str, trigger: str) -> str:
    return (f"a {tool} command from the harness worktree {name} names a script and also holds "
            f"{trigger!r} (a heredoc or here-string marker, or a backslash-newline), so the hook "
            "cannot tell which file runs (261109-gzy); run the script by a plain path from the "
            "worktree root, in a call of its own")  # fmt: skip


def _bare_quoting(tool: str, text: str) -> str:
    """261112-fdw: the first `$'` (an ANSI-C quote) or `#` (it may start a comment) outside
    quotes, which the word reader does not follow, or ''. An escaped character is skipped."""
    escape = "\\" if tool == "Bash" else "`"
    quote, index = "", 0
    while index < len(text):
        char = text[index]
        if char == escape and quote != "'":
            index += 2
            continue
        if quote:
            quote = "" if char == quote else quote
        elif text.startswith("$'", index):
            return "$'"
        elif char == "#":
            return "#"
        elif char in "'\"":
            quote = char
        index += 1
    return ""


def _quoting(tool: str, name: str, trigger: str) -> str:
    return (f"a {tool} command from the harness worktree {name} names a script and also holds "
            f"{trigger!r} outside quotes (an ANSI-C quote, or a `#` that may start a comment), so "
            "the hook cannot tell which file runs (261109-gzy, 261112-fdw); run the script by a "
            "plain path from the worktree root, in a call of its own")  # fmt: skip


def _worktree_command(payload: Mapping) -> Decision:
    """A Bash or PowerShell call from a harness worktree (the payload cwd under
    .claude/worktrees/<name>/) is denied when its command, or a script file it names, spells
    the main checkout's absolute path, or when such a script cannot be scanned (_scripts_denial).
    A call that names a script passes only when every command in it has a listed shape
    (_allowlist_denial, 261112-fdw). Every other shell call gets no opinion, decided before
    tool_input is read."""
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        raise HookError("the payload has no cwd string, so the hook cannot tell a worktree "
                        "session from the main one")  # fmt: skip
    pairs = _worktree_pairs(cwd)
    if not pairs:
        return NO_OPINION
    tool = payload["tool_name"]
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, Mapping) else None
    if not isinstance(command, str):
        raise HookError(f"the {tool} payload has no command string")
    main, name = pairs[0]
    if _spells_main(command, pairs):
        return _deny(f"a {tool} command from the harness worktree {name} {_spells(main)}")
    text = command.translate(_POWERSHELL_QUOTES) if tool == "PowerShell" else command
    words = _script_words(tool, text)
    contents = _substitutions(tool, text)
    for content in contents:
        words.extend(_script_words(tool, content))
    if not words and not _SCRIPT_MENTION.search(command):
        return NO_OPINION
    trigger = _INDIRECTION.search(command)
    if trigger is not None:
        return _deny(_indirect(tool, name, trigger.group()))
    quoting = next(filter(None, (_bare_quoting(tool, part) for part in [text, *contents])), "")
    reason =(_scripts_denial(words, cwd, tool, pairs)
              or (_quoting(tool, name, quoting) if quoting else "")
              or _allowlist_denial(tool, text, cwd, name))  # fmt: skip
    judged = (_allowlist_denial(tool, content, cwd, name, nested=True) for content in contents)
    reason = reason or next((found for found in judged if found), "")
    return _deny(reason) if reason else NO_OPINION


# --- the drive write guard (todo drive-write-guard) ------------------------------------------

# Security review: under a live drive, a shell call that runs in or names its checkout runs only
# listed read shapes (default deny). Commands that read, list or print and write nothing, as
# _command_name gives them (Bash and PowerShell names and aliases):
_DRIVE_READS = frozenset({
    "cat", "head", "tail", "ls", "dir", "grep", "wc", "diff", "cmp", "echo", "printf", "test",
    "[", "true", "false", "pwd", "sleep", "basename", "dirname", "realpath", "readlink", "stat",
    "du", "df", "which", "cut", "tr", "ps", "tasklist", "type",
    "get-content", "gc", "select-object", "select", "select-string", "sls", "get-childitem", "gci",
    "get-item", "gi", "test-path", "get-location", "gl", "resolve-path", "rvpa", "split-path",
    "join-path", "get-filehash", "get-date", "get-process", "gps", "get-ciminstance", "gcim",
    "where-object", "where", "?", "measure-object", "measure", "sort-object", "format-table",
    "ft", "format-list", "fl", "out-string", "write-output", "write-host", "compare-object",
    "convertfrom-json", "convertto-json", "start-sleep",
})  # fmt: skip
# todo drive-hook-read-only-verbs: find may run a listed read on what it finds, up to `;` or `+`.
_FIND_RUNS = frozenset({"-exec", "-execdir"})
_FIND_ENDS = frozenset({";", "+"})
# date sets the clock with -s/--set or a bare operand; these options take the next word as data.
_DATE_VALUES = frozenset({"-d", "--date", "-f", "--file", "-r", "--reference"})
_DATE_VALUE_LETTERS = frozenset("dfr")
_DATE_INLINE = "I"  # -I[FMT]: the rest of the bundle is its value


def _drive_find_offender(args: Sequence[str]) -> str:
    """find under a drive: no action of _FIND_REFUSED but -exec and -execdir whose program is a
    listed read, its words up to `;` or `+`. A `\\;` the splitter took for a separator ends the
    command there, and the words after it are judged as a command of their own."""
    index = 0
    while index < len(args):
        word = args[index]
        index += 1
        if word not in _FIND_RUNS:
            if word in _FIND_REFUSED:
                return word
            continue
        if index == len(args) or _command_name(args[index]) not in _DRIVE_READS:
            return args[index] if index < len(args) else word
        while index < len(args) and args[index] not in _FIND_ENDS:
            index += 1
        index += 1
    return ""


def _date_offender(args: Sequence[str]) -> str:
    """date prints, as long as it is not told to set the clock: -s or --set (in any bundle or
    abbreviation) and a bare operand (MMDDhhmm) are refused; `+FORMAT` and the values of -d, -f
    and -r are data."""
    value = False
    for word in args:
        if value or word.startswith("+"):
            value = False
            continue
        if word.startswith("--"):
            if word.startswith("--s"):
                return word
            value = word in _DATE_VALUES  # `--date=x` carries its value
            continue
        if not word.startswith("-") or word == "-":
            return word
        for at, letter in enumerate(word[1:], start=2):
            if letter == "s":
                return word
            if letter in _DATE_VALUE_LETTERS or letter == _DATE_INLINE:
                value = letter != _DATE_INLINE and at == len(word)
                break
    return ""


_DRIVE_CHECKS = {"find": _drive_find_offender, "sed": _sed_offender,
                 "date": _date_offender}  # reads only in these shapes  # fmt: skip
# Commands that remove, create or change the files they name, beside _WRITERS: listed only when
# none of their operands may lie under the checkout.
_REMOVERS = frozenset({
    "rm", "rmdir", "mkdir", "md", "del", "erase", "rd", "ri", "remove-item", "rename-item", "rni",
    "ren", "unlink", "clear-content", "clc", "chmod", "truncate", "patch",
})  # fmt: skip
# Words that only steer the commands after them; a loop's head words are data, not a program.
_BASH_KEYWORDS = frozenset({"if", "then", "else", "elif", "fi", "do", "done", "while", "until",
                            "esac", "!", "{", "}"})  # fmt: skip
_BASH_LOOPS = frozenset({"for", "case", "select"})
_POWERSHELL_KEYWORDS = frozenset({"if", "else", "elseif", "while", "do", "until", "for",
                                  "foreach", "switch", "try", "catch", "finally",
                                  "foreach-object", "%"})  # fmt: skip
# A PowerShell variable or property read ($p, $_.CommandLine, $env:X), and a method call, which
# a call that touches the checkout may not make ($_.Delete(), [IO.File]::WriteAllText(...)).
_POWERSHELL_VALUE = re.compile(r"\$(?:env:)?\w+(?:\.\w+)*")
_POWERSHELL_CALL = re.compile(r"(?:\.|::)\s*[A-Za-z_]\w*\s*\(")
# Shells and evaluators whose command text is judged as a call of its own (security review 4).
_NESTED_SHELLS = {"bash": "Bash", "sh": "Bash", "eval": "Bash", "pwsh": "PowerShell",
                  "powershell": "PowerShell", "iex": "PowerShell",
                  "invoke-expression": "PowerShell", "cmd": "PowerShell"}  # fmt: skip
_EVALUATORS = frozenset({"eval", "iex", "invoke-expression"})  # their operands are the text
_BASH_VALUE_OPTIONS = frozenset({"-o", "+o", "-O", "+O"})  # these take the next word
_POWERSHELL_COMMAND = "command"  # -Command and each prefix of it (-c, -Comm)
_POWERSHELL_COMMAND_ALIASES = frozenset({"cwa"})  # -CommandWithArgs
_POWERSHELL_ENCODED = "encodedcommand"  # -EncodedCommand, its prefixes (-e) and -ec
_POWERSHELL_ENCODED_ALIASES = frozenset({"ec"})
_POWERSHELL_FILE = "file"  # -File and its prefixes: a script
_CMD_COMMAND_FLAGS = frozenset({"/c", "/k", "/r"})
_MOVES = frozenset({"cd", "pushd", "chdir", "set-location", "sl", "push-location"})
_RETURNS = frozenset({"popd", "pop-location"})  # back to a directory the hook does not track
_NULL_DEVICES = frozenset({"/dev/null", "nul", "$null"})
_UNPLACED = re.compile(r"[$`%]|^~")  # a variable, escape or home: the hook cannot place the path
# The one program shape: `uv run --no-project python <flags> <script>`, the script outside every
# live checkout (CLAUDE.md, Drives: scratchpad scripts that read).
_UV_NO_PROJECT = "--no-project"  # `uv run --no-project` neither syncs nor builds the checkout
_UV_READ_OPTIONS = frozenset({_UV_NO_PROJECT, "--quiet", "-q"})
_PYTHONS = frozenset({"python", "python3", "py"})
_PYTHON_READ_FLAGS = frozenset({"-I", "-B", "-E", "-s", "-S", "-u", "-O", "-OO", "-q"})
# git subcommands that never write; the refreshing ones update the index unless told not to.
_GIT_READS = frozenset({
    "blame", "cat-file", "check-ignore", "for-each-ref", "log", "ls-files", "ls-tree",
    "merge-base", "rev-list", "rev-parse", "shortlog", "show", "show-ref", "version",
})  # fmt: skip
_GIT_REFRESHES = frozenset({"status", "diff", "describe"})
_GIT_NO_LOCKS = "--no-optional-locks"
_GIT_GLOBALS = frozenset({_GIT_NO_LOCKS, "--no-pager", "-P"})  # with -C, all a call may pass
# The clone out of the checkout: value-free options only, then the source and the destination.
_GIT_CLONE_OPTIONS = frozenset({"--no-hardlinks", "--local", "-l", "--no-checkout", "-n",
                                "--quiet", "-q"})  # fmt: skip
_CLONE_OPERANDS = 2
# todo drive-hook-read-only-verbs: a copy, archive or fetch reads the checkout when only what it
# writes is judged. GNU cp's value-free letters (no -l or -s links, no -b backups), its target
# directory option, and PowerShell's Copy-Item parameters as written in full:
_CP_LETTERS = frozenset("rRpvfnuLT")
_CP_TARGET_LETTER = "t"
_CP_TARGET = "--target-directory"
_CP_LONG = frozenset({"--recursive", "--verbose", "--force", "--no-clobber", "--dereference"})
_POWERSHELL_COPIES = frozenset({"copy-item", "cpi", "copy", "cp"})
_COPY_ITEM_SOURCES = frozenset({"-path", "-literalpath"})
_COPY_ITEM_DESTINATION = "-destination"
_COPY_ITEM_SWITCHES = frozenset({"-recurse", "-force", "-container"})
# tar in dash bundles only: one mode, value-free letters, and -f/-C with their values.
_TAR_MODES = frozenset("ctx")
_TAR_EXTRACT = "x"
_TAR_LETTERS = frozenset("vzjJ")
_TAR_ARCHIVE = "f"
_TAR_DIRECTORY = "C"
_TAR_EXCLUDE = "--exclude="
_STDIO = "-"
_GIT_FETCHES = frozenset({"fetch", "pull"})
_GIT_FETCH_OPTIONS = frozenset({"--ff-only", "--no-rebase", "--prune", "--tags", "--no-tags",
                                "--quiet", "-q", "--verbose", "-v"})  # fmt: skip
# PowerShell `$name = <literal>`: a quoted string with no expansion, or a number.
_POWERSHELL_LITERAL = re.compile(r"""\$\w+\s*=\s*(?:'[^']*'|"[^"`$]*"|\d+(?:\.\d+)?)""")
_AND = "&&"  # the one separator after which a cd has surely moved the next command
# todo image-build-during-drive: the compose image name is fixed, so a build anywhere re-tags the
# image a running drive recorded. docker's and compose's options before the subcommand (one in a
# *_VALUES set takes the next word; any other unlisted option fails closed, as a build).
_DOCKERS = frozenset({"docker", "docker-compose"})
_COMPOSE = "compose"
_DOCKER_COMPOSE = "docker-compose"
_DOCKER_VALUES = frozenset({"-c", "--context", "-H", "--host", "--config", "-l", "--log-level",
                            "--tlscacert", "--tlscert", "--tlskey"})  # fmt: skip
_DOCKER_FLAGS = frozenset({"-D", "--debug", "--tls", "--tlsverify", "-v", "--version", "--help"})
_COMPOSE_VALUES = frozenset({"-f", "--file", "-p", "--project-name", "--project-directory",
                             "--env-file", "--profile", "--ansi", "--progress",
                             "--parallel"})  # fmt: skip
_COMPOSE_FLAGS = frozenset({"--dry-run", "--compatibility", "--all-resources", "--help", "-v",
                            "--version"})  # fmt: skip
_DOCKER_IMAGE = "image"  # `docker image <sub>`: the same subcommands under a group
_IMAGE_BUILDERS = frozenset({"build", "buildx", "builder"})
_DOCKER_TAG = "tag"
_COMPOSE_BUILDS = frozenset({"build", "watch"})
_COMPOSE_RUNS = frozenset({"run", "up", "create"})  # these build when given --build
_COMPOSE_BUILD_FLAG = "--build"
_SHARED_IMAGE = "reverseapoc-build"  # reverseapoc-build:local, the tag a retag would move
# todo image-guard-other-retags (owner ruling 2026-11-24): these move a tag when they name the
# shared image; `load` takes its tags from the tarball, so every load counts.
_DOCKER_GROUPS = frozenset({_DOCKER_IMAGE, "container"})
_IMAGE_RETAGS = frozenset({_DOCKER_TAG, "commit", "import", "pull"})
_IMAGE_LOAD = "load"
# todo hook-script-files (owner ruling 2026-11-24): the hook judges a command line, not what a
# script or a -Command text does, so under a live drive PowerShell runs nothing from any cwd:
# directly, through cmd /c or a nested shell, or handed to one of these launchers.
_POWERSHELLS = frozenset({"powershell", "pwsh"})
_LAUNCHERS = frozenset({"start-process", "saps", "start", "timeout", "env", "xargs", "nohup",
                        "exec", "nice"})  # fmt: skip
# The repo's own helpers stand in for the operator's scripts: `uv run reverseapoc <helper> RUN`,
# then at most the helper's one option and its value.
_DRIVE_HELPERS = {"drive-stop": "--wait-minutes", "drive-status": "--log"}
_HELPER_COUNT = "--wait-minutes"  # its value is a whole number of minutes
_HELPER_WORDS = 3  # reverseapoc, the helper, RUN
_HELPER_OPTION_WORDS = 2  # the option and its value
_RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _ancestors(starts: Iterable[Path]) -> Iterator[Path]:
    """Each of `starts` and every ancestor of it, once."""
    seen: set[str] = set()
    for start in starts:
        for directory in (start, *start.parents):
            key = directory.as_posix().casefold()
            if key not in seen:
                seen.add(key)
                yield directory


def _live_drives(starts: Iterable[Path]) -> tuple[str, ...]:
    """The checkouts among `starts` and their ancestors whose build/driver/drive.lock a live
    process holds (locks.is_held; a lock file left behind by an exited drive is stale and does
    not count), as forward-slash forms."""
    return tuple(d.as_posix() for d in _ancestors(starts) if is_held(d / DRIVE_LOCK))


def _drive_denial(root: str, what: str) -> Decision:
    return _deny(f"a reverseapoc drive holds {root}/{DRIVE_LOCK.as_posix()}, so {what} is "
                 "refused: nothing may write under that checkout, nor run tests, uv, docker or "
                 "the CLI there, until the drive process exits (CLAUDE.md, Drives: its audit "
                 "restores such writes and stops the night). Reads stay open (git with "
                 f"{_GIT_NO_LOCKS}); for a change, clone outside the checkout (git clone "
                 "--no-hardlinks <checkout> <scratchpad>/<name>) and edit, test and commit in "
                 "the clone, as `cd <clone> && <command>`")  # fmt: skip


def _drive_edit(tool: str, raw: str, paths: Sequence[str], env: Mapping[str, str]) -> Decision:
    """An edit is refused while a live drive holds the lock of a checkout above its target. The
    driver's own sessions carry their claim and are bound by the matching layer instead."""
    if _claim(env) is not None:
        return NO_OPINION
    live = _live_drives(Path(path).parent for path in paths)
    return _drive_denial(live[0], f"the {tool} of {raw!r}") if live else NO_OPINION


def _drive_command(payload: Mapping, env: Mapping[str, str]) -> Decision:
    """A Bash or PowerShell call is refused while a live drive holds the lock of the checkout
    its cwd or the session's project lies in, when _drive_offender names an offender. Any other
    call, and every call with no live drive, gets no opinion, decided before the command is
    parsed."""
    if _claim(env) is not None:
        return NO_OPINION
    here = candidates(_cwd(payload))  # _worktree_command refused a payload without a cwd
    project = project_roots(env) if env.get(PROJECT_ENV) else ()
    live = _live_drives(Path(form) for form in (*here, *project))
    if not live:
        return NO_OPINION
    tool = payload["tool_name"]
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, Mapping) else None
    if not isinstance(command, str):
        raise HookError(f"the {tool} payload has no command string")
    try:
        offender = _drive_offender(tool, command, here[0], live)
    except _ImageBuild as build:
        return _image_denial(live[0], str(build))
    except _ScriptRun as run:
        return _powershell_denial(live[0], str(run))
    return _drive_denial(live[0], f"the {tool} command's {offender!r}") if offender else NO_OPINION


class _ImageBuild(Exception):  # noqa: N818 -- a verdict, not an error: the call is refused
    """A docker image build or retag found anywhere in a call (a nested shell's or
    substitution's text included): refused from every cwd under a live drive, with its own
    reason."""


class _ScriptRun(Exception):  # noqa: N818 -- a verdict, not an error: the call is refused
    """A PowerShell run found anywhere in a call: refused from every cwd under a live drive,
    with its own reason (todo hook-script-files)."""


def _powershell_denial(root: str, run: str) -> Decision:
    return _deny(f"a reverseapoc drive holds {root}/{DRIVE_LOCK.as_posix()}, so the PowerShell "
                 f"run {run!r} is refused from any directory, a clone included: the hook judges "
                 "a command line, not what a -File script or a -Command text does, so such a run "
                 "could write under the checkout unseen (todo hook-script-files, owner ruling "
                 "2026-11-24). To stop or watch the drive use `uv run reverseapoc drive-stop RUN "
                 "[--wait-minutes N]` or `uv run reverseapoc drive-status RUN [--log PATH]`; run "
                 "other scripts after the drive process exits")  # fmt: skip


def _image_denial(root: str, build: str) -> Decision:
    return _deny(f"a reverseapoc drive holds {root}/{DRIVE_LOCK.as_posix()}, so the image build "
                 f"or retag {build!r} is refused from any directory, a clone included: the "
                 "compose image name is fixed, so a build, tag, commit, import, pull or load can "
                 "move the shared reverseapoc-build:local tag whose id the running drive "
                 "recorded in STARTED (run 20261120-codex lost its digest that way). Build after "
                 "the drive process exits (docs/toolchain.md); `docker compose run --rm -T build "
                 "...` from a clone still works")  # fmt: skip


def _past_options(words: Sequence[str], values: frozenset[str],
                  flags: frozenset[str]) -> Sequence[str] | None:  # fmt: skip
    """`words` from the first one that is not an option: one in `values` takes the next word,
    `--opt=value` and one in `flags` none; None at any other option, since it may take a value
    and hide the subcommand."""
    index = 0
    while index < len(words) and words[index].startswith("-"):
        word = words[index]
        if word in values:
            index += 2
        elif word in flags or (word.startswith("--") and "=" in word):
            index += 1
        else:
            return None
    return words[index:]


def _image_build(name: str, rest: Sequence[str]) -> bool:
    """Whether a docker or docker-compose call builds or re-tags an image: build, buildx,
    builder or `image build`, any load, a tag, commit, import or pull naming reverseapoc-build
    (each also under `image` or `container`), or a compose build (_compose_build); an unlisted
    option before the subcommand counts as one."""
    if name == _DOCKER_COMPOSE:
        return _compose_build(rest)
    words = _past_options(rest, _DOCKER_VALUES, _DOCKER_FLAGS)
    if words is None:
        return True
    sub, args = (words[0], words[1:]) if words else ("", ())
    if sub == _COMPOSE:
        return _compose_build(args)
    if sub in _DOCKER_GROUPS:
        sub, args = (args[0], args[1:]) if args else ("", ())
    if sub in _IMAGE_BUILDERS or sub == _IMAGE_LOAD:
        return True
    return sub in _IMAGE_RETAGS and any(_SHARED_IMAGE in word.casefold() for word in args)


def _compose_build(rest: Sequence[str]) -> bool:
    """`compose build` or `watch`, or `run`, `up` or `create` with --build anywhere after it."""
    words = _past_options(rest, _COMPOSE_VALUES, _COMPOSE_FLAGS)
    if words is None:
        return True
    if not words:
        return False
    sub, args = words[0], words[1:]
    built = any(word.split("=", 1)[0] == _COMPOSE_BUILD_FLAG for word in args)
    return sub in _COMPOSE_BUILDS or (sub in _COMPOSE_RUNS and built)


@dataclass(frozen=True)
class _Run:
    """One simple command of a shell call, as the drive guard judges it."""

    word: str  # its program word as written: the offender a denial names
    here: str | None  # the directory it runs in (None: unknown, judged as inside)
    words: tuple[str, ...]  # the operands, option values and assignment values it names
    read: bool  # whether it has a listed read shape


def _drive_offender(tool: str, command: str, here: str | None, live: tuple[str, ...]) -> str:
    """The word that refuses `command` under a live drive, or '': a redirection into the
    checkout, a git global option or an unreadable nested command anywhere; and, when the call
    runs in or names the checkout (any command of it, a substitution's included), any command
    without a listed read shape, or a PowerShell method call. `here` is the directory the shell
    starts in (None: unknown, judged as inside); each cd moves it for the commands after it."""
    text = command.translate(_POWERSHELL_QUOTES) if tool == "PowerShell" else command
    runs: list[_Run] = []
    for part in (text, *_substitutions(tool, text)):
        found = _collect_runs(tool, part, here, live, runs)
        if found:
            return found
    if not any(_touches(run, live) for run in runs):
        return ""
    call = _POWERSHELL_CALL.search(text) if tool == "PowerShell" else None
    if call is not None:
        return call.group()
    return next((run.word for run in runs if not run.read), "")


def _collect_runs(tool: str, part: str, here: str | None, live: tuple[str, ...],
                  runs: list[_Run]) -> str:  # fmt: skip
    """Append the runs of `part`'s simple commands to `runs`; the offender refused anywhere, or
    ''. A cd moves the commands after it only across `&&` (after `;`, `||` or a pipe they may
    run where it failed or left them), and a Bash subshell's moves end with it."""
    subshells: list[str | None] = []
    for segment, separator in _separated(tool, part):
        before = here
        here, run, found = _drive_segment(tool, segment, here, live)
        if found:
            return found
        if run is not None:
            runs.append(run)
        if here != before and separator.strip() != _AND:
            here = None
        if tool == "Bash":
            here = _subshell_moves(separator, here, subshells)
    return ""


def _subshell_moves(separator: str, here: str | None, subshells: list[str | None]) -> str | None:
    """Where a Bash shell is after `separator`'s parentheses: each `(` keeps the directory to go
    back to, each `)` returns there (None when unbalanced)."""
    for char in separator:
        if char == "(":
            subshells.append(here)
        elif char == ")":
            here = subshells.pop() if subshells else None
    return here


def _touches(run: _Run, live: tuple[str, ...]) -> bool:
    """Whether a run is in, or names a path that may lie under, a live drive's checkout."""
    return _guarded_dir(run.here, live) or any(_guarded(word, run.here, live)
                                               for word in run.words if word)  # fmt: skip


def _redirected(tool: str, segment: Sequence[tuple[str, bool]]) -> tuple[list[str], list[str]]:
    """One simple command's words (detection forms) and the files its output redirections
    write; an input redirection's file, a duplicated descriptor (`2>&1`) and PowerShell's
    `N>&M` are neither."""
    words, written, pending = [], [], None
    for text, op in segment:
        if op:
            takes = tool == "Bash" or not text[-1].isdigit()
            pending = (">" in text, text.endswith("&")) if takes else None
            continue
        word = _plain(tool, text)
        if pending is None:
            words.append(word)
            continue
        (output, duplicate), pending = pending, None
        if output and not (duplicate and (word.isdigit() or word == "-")):
            written.append(word)
    return words, written


def _assigned(tool: str, words: Sequence[str]) -> tuple[tuple[str, ...], Sequence[str]]:
    """Bash's leading NAME=value words split off: (their values, the words after them)."""
    if tool != "Bash":
        return (), words
    index = 0
    while index < len(words) and _BASH_ASSIGNMENT.match(words[index]):
        index += 1
    return tuple(word.split("=", 1)[1] for word in words[:index]), words[index:]


def _past_keywords(tool: str, words: Sequence[str]) -> Sequence[str]:
    keywords = _BASH_KEYWORDS if tool == "Bash" else _POWERSHELL_KEYWORDS
    index = 0
    while index < len(words) and words[index].casefold() in keywords:
        index += 1
    return words[index:]


def _drive_segment(
    tool: str, segment: Sequence[tuple[str, bool]], here: str | None, live: tuple[str, ...]
) -> tuple[str | None, _Run | None, str]:
    """(where the shell is after one simple command, its run or None, the offender refused
    anywhere or '')."""
    words, written = _redirected(tool, segment)
    found = _first(written, lambda word: _guarded(word, here, live))
    if found:
        return here, None, found
    raw = " ".join(text for text, op in segment if not op)
    if tool == "PowerShell" and _POWERSHELL_LITERAL.fullmatch(raw):
        return here, _Run(words[0], here, (), True), ""  # data; a later $name is unplaceable
    values, words = _assigned(tool, words)
    words = _past_keywords(tool, words)
    if not words:
        return here, (_Run("", here, values, True) if values else None), ""
    head, rest = words[0], words[1:]
    name = _command_name(head)
    if name in _POWERSHELLS or (name in _LAUNCHERS
                                and any(_command_name(word) in _POWERSHELLS for word in rest)):
        raise _ScriptRun(" ".join(words))
    if name in _DOCKERS and _image_build(name, rest):
        raise _ImageBuild(" ".join(words))
    if name in _MOVES:
        return _moved(rest, here), None, ""
    if name in _RETURNS:
        return None, None, ""
    if name == "git":
        run, found = _git_run(head, rest, here, values, live)
        return here, run, found
    if name in _NESTED_SHELLS:
        readable, found = _nested(head, name, rest, here, live)
        named = values if readable else (*values, *_operands(rest))
        return here, _Run(head, here, tuple(named), readable), found
    loop = tool == "Bash" and name in _BASH_LOOPS  # `for f in <words>`: data, not a program
    # a NAME=value before uv (UV_PROJECT_ENVIRONMENT, PYTHONPATH) steers what it runs or writes
    read = loop or (_read_shape(tool, words, here, live) and not (values and name == "uv"))
    return here, _Run(head, here, (*values, *(rest if loop else _operands(rest))), read), ""


def _read_shape(tool: str, words: Sequence[str], here: str | None, live: tuple[str, ...]) -> bool:
    """Whether a command (its program word first) has a listed read shape: a listed read, find,
    sed or date in their reading shapes, a copy or tar whose writes land outside every live
    checkout, a writer none of whose operands may lie under the checkout, the uv script shape,
    or a PowerShell variable read or assignment of a read."""
    name, rest = _command_name(words[0]), words[1:]
    if name in _DRIVE_READS:
        return True
    if name in _DRIVE_CHECKS:
        return not _DRIVE_CHECKS[name](rest)
    if name == "tar":
        return _tar_read(rest, here, live)
    copy = (_copy_item_targets(rest) if tool == "PowerShell" and name in _POWERSHELL_COPIES
            else _cp_targets(rest) if tool == "Bash" and name == "cp" else None)  # fmt: skip
    if copy and not any(_guarded(word, here, live) for word in copy):
        return True
    if name in _WRITERS or name in _REMOVERS:
        return not any(_guarded(word, here, live) for word in _operands(rest) if word)
    if name == "uv":
        return _uv_read(rest, here, live)
    if tool == "PowerShell" and _POWERSHELL_VALUE.fullmatch(name):
        value = rest[1:] if rest[:1] == ["="] else ()
        return not value or _read_shape(tool, value, here, live)
    return False


def _cp_targets(rest: Sequence[str]) -> list[str] | None:
    """What a GNU cp writes: every -t directory, else its last operand (after at least one
    source); None when it passes an option beside the listed ones."""
    targets, operands, words = [], [], iter(rest)
    for word in words:
        if word == "--":
            operands.extend(words)
        elif word.startswith(_CP_TARGET + "="):
            targets.append(word.split("=", 1)[1])
        elif word == _CP_TARGET:
            targets.append(next(words, ""))
        elif word in _CP_LONG:
            continue
        elif word.startswith("--"):
            return None
        elif word.startswith("-") and word != _STDIO:
            flags, target, value = word[1:].partition(_CP_TARGET_LETTER)
            if not set(flags) <= _CP_LETTERS:
                return None
            if target:
                targets.append(value or next(words, ""))
        else:
            operands.append(word)
    if targets:
        return targets if operands else None
    return operands[-1:] if len(operands) > 1 else None


def _copy_item_targets(rest: Sequence[str]) -> list[str] | None:
    """What Copy-Item writes: its -Destination, by name or by position (after -Path, by name or
    first); None for any other parameter, or a call without a destination."""
    named, positional, words = [], [], iter(rest)
    slots = ["path", "destination"]
    for word in words:
        key = word.casefold()
        if key == _COPY_ITEM_DESTINATION:
            named.append(next(words, ""))
            slots = [slot for slot in slots if slot != "destination"]
        elif key in _COPY_ITEM_SOURCES:
            next(words, None)
            slots = [slot for slot in slots if slot != "path"]
        elif key in _COPY_ITEM_SWITCHES:
            continue
        elif word.startswith("-"):
            return None
        else:
            positional.append(word)
    if len(positional) > len(slots):
        return None
    bound = zip(slots, positional, strict=False)  # fewer positionals than slots leave some free
    targets = [*named, *(word for slot, word in bound if slot == "destination")]
    return targets or None


def _tar_read(rest: Sequence[str], here: str | None, live: tuple[str, ...]) -> bool:
    """tar in dash bundles of one mode (create, list or extract), v, z, j, J, -f and -C, and
    --exclude=PATTERN: no archive (-f, read or written) under a live checkout, and an extract
    lands outside it: every -C, each relative to the last, and the cwd when no -C comes before
    the first member it names."""
    modes, archives, dirs, member_first = set(), [], [], False
    words = iter(rest)
    for word in words:
        if word.startswith(_TAR_EXCLUDE):
            continue
        if not word.startswith("-") or word == _STDIO:
            member_first = member_first or not dirs
            continue
        if word.startswith("--"):
            return False
        for at, letter in enumerate(word[1:], start=2):
            if letter in (_TAR_ARCHIVE, _TAR_DIRECTORY):
                value = word[at:] or next(words, "")
                (archives if letter == _TAR_ARCHIVE else dirs).append(value)
                break
            if letter in _TAR_MODES:
                modes.add(letter)
            elif letter not in _TAR_LETTERS:
                return False
    if len(modes) != 1 or any(_guarded(path, here, live) for path in archives if path != _STDIO):
        return False
    if _TAR_EXTRACT not in modes:
        return True
    if (member_first or not dirs) and _guarded_dir(here, live):
        return False
    for directory in dirs:
        here = _moved([directory], here)
        if _guarded_dir(here, live):
            return False
    return True


def _operands(rest: Sequence[str]) -> Iterator[str]:
    """A command's operands: every word but an option, and the value of an `--opt=value`."""
    for word in rest:
        if not word.startswith("-"):
            yield word
        elif "=" in word:
            yield word.split("=", 1)[1]


def _uv_read(rest: Sequence[str], here: str | None, live: tuple[str, ...]) -> bool:
    """`uv run --no-project [-q] python [<flags>] <script> ...` with the script outside every
    live checkout: the scratchpad script the coordinator may run during a drive; or one of the
    repo's drive helpers (_drive_helper)."""
    if rest[:1] != ["run"]:
        return False
    if _drive_helper(rest[1:]):
        return True
    options = list(itertools.takewhile(lambda word: word.startswith("-"), rest[1:]))
    if _UV_NO_PROJECT not in options or not set(options) <= _UV_READ_OPTIONS:
        return False
    program = rest[1 + len(options) :]
    if not program or _command_name(program[0]) not in _PYTHONS:
        return False
    flags = list(itertools.takewhile(lambda word: word.startswith("-"), program[1:]))
    script = program[1 + len(flags) :][:1]
    return (set(flags) <= _PYTHON_READ_FLAGS and bool(script)
            and not _guarded(script[0], here, live))  # fmt: skip


def _drive_helper(words: Sequence[str]) -> bool:
    """`reverseapoc drive-stop RUN [--wait-minutes N]` or `reverseapoc drive-status RUN [--log
    PATH]` after `uv run` with no uv option: the repo's helpers that stop or watch a drive
    (todo hook-script-files, owner ruling 2026-11-24)."""
    if len(words) < _HELPER_WORDS:
        return False
    program, helper, run, *extra = words
    if program != "reverseapoc" or helper not in _DRIVE_HELPERS or not _RUN_NAME.fullmatch(run):
        return False
    if not extra:
        return True
    option = _DRIVE_HELPERS[helper]
    if len(extra) != _HELPER_OPTION_WORDS or extra[0] != option:
        return False
    return extra[1].isdigit() if option == _HELPER_COUNT else not extra[1].startswith("-")


def _git_run(word: str, rest: Sequence[str], here: str | None, values: tuple[str, ...],
             live: tuple[str, ...]) -> tuple[_Run | None, str]:  # fmt: skip
    """git's run, its words judged where `-C` moves it; any global option but -C,
    --no-optional-locks, --no-pager and -P (--git-dir, --work-tree, -c) is refused wherever
    the shell runs (security review 2). It reads when its subcommand never writes there: a
    read, a listing, status, diff and describe with --no-optional-locks (plain `git status`
    takes the index lock), or the clone the denial names (_git_clone_out)."""
    index, no_locks = 0, False
    while index < len(rest) and rest[index].startswith("-"):
        option = rest[index]
        index += 1
        if option == "-C" and index < len(rest):
            here, index = _moved(rest[index : index + 1], here), index + 1
        elif option in _GIT_GLOBALS:
            no_locks = no_locks or option == _GIT_NO_LOCKS
        else:
            return None, option
    command = rest[index:]
    read = bool(command) and (not _git_read_offender(command, no_locks)
                              or _git_clone_out(command, here, live)
                              or (not values and _git_fetch_in(command, here, live)))  # fmt: skip
    return _Run(word, here, (*values, *_operands(command)), read), ""


def _git_fetch_in(command: Sequence[str], here: str | None, live: tuple[str, ...]) -> bool:
    """`git fetch` or `git pull` with listed value-free options only, run in a repository outside
    every live checkout: it writes there and only reads the remote it names, the checkout
    included (todo drive-hook-read-only-verbs). The caller refuses it after a NAME=value word,
    which could point GIT_DIR into the checkout."""
    options = {word for word in command[1:] if word.startswith("-")}
    return (command[0] in _GIT_FETCHES and options <= _GIT_FETCH_OPTIONS
            and not _guarded_dir(here, live))  # fmt: skip


def _git_clone_out(command: Sequence[str], here: str | None, live: tuple[str, ...]) -> bool:
    """`git clone [--no-hardlinks ...] <source> <dest>` with `dest` outside every live
    checkout: it only reads the source (the route _drive_denial names)."""
    if command[0] != "clone":
        return False
    options = [word for word in command[1:] if word.startswith("-")]
    operands = [word for word in command[1:] if not word.startswith("-")]
    return (set(options) <= _GIT_CLONE_OPTIONS and len(operands) == _CLONE_OPERANDS
            and not _guarded(operands[-1], here, live))  # fmt: skip


def _git_read_offender(command: Sequence[str], no_locks: bool) -> str:
    sub, args = command[0], command[1:]
    if sub in _GIT_READS or (sub in _GIT_REFRESHES and no_locks):
        return _first(args, _git_refused)
    return _git_listing_offender(sub, args)


def _nested(word: str, name: str, rest: Sequence[str], here: str | None,
            live: tuple[str, ...]) -> tuple[bool, str]:  # fmt: skip
    """A nested shell or evaluator (security review 4): (True, its offender) when it runs a
    command text, judged as a call of its own; (True, `word`) when that text is encoded or
    cannot be parsed, refused anywhere; (False, '') when it runs a script or reads stdin, which
    has no read shape."""
    text, encoded = _nested_text(name, rest)
    if encoded:
        return True, word
    if text is None:
        return False, ""
    try:
        return True, _drive_offender(_NESTED_SHELLS[name], text, here, live)
    except HookError:
        return True, word


def _nested_text(name: str, rest: Sequence[str]) -> tuple[str | None, bool]:
    """(the command text a nested shell runs, None for a script or stdin; whether it is
    encoded). cmd's text is read with the PowerShell splitter, which knows its `&`, `|` and
    `>`."""
    if name in _EVALUATORS:
        return " ".join(word for word in rest if not word.startswith("-")), False
    if name == "cmd":
        flag = next((i for i, word in enumerate(rest) if word.casefold() in _CMD_COMMAND_FLAGS),
                    None)  # fmt: skip
        return (None if flag is None else " ".join(rest[flag + 1 :])), False
    if _NESTED_SHELLS[name] == "Bash":
        return _bash_text(rest), False
    return _powershell_text(rest)


def _bash_text(rest: Sequence[str]) -> str | None:
    """bash's command string: the first operand after options, when a short-option bundle holds
    `c` (-c, -lc, -ec); None for a script or stdin."""
    command, index = False, 0
    while index < len(rest):
        word = rest[index]
        index += 1
        if word in _BASH_VALUE_OPTIONS:
            index += 1
        elif word.startswith("-") and not word.startswith("--"):
            command = command or "c" in word[1:]
        elif not word.startswith(("--", "+")):
            return word if command else None
    return None


def _powershell_text(rest: Sequence[str]) -> tuple[str | None, bool]:
    """PowerShell's command text: everything after -Command or a prefix of it (-c, -Comm) or
    -CommandWithArgs; encoded after -EncodedCommand, a prefix of it (-e) or -ec; None for -File
    (or a prefix of it), a positional script or stdin."""
    for index, word in enumerate(rest):
        param = word[1:].casefold() if word.startswith("-") else ""
        if not param:
            continue
        if _POWERSHELL_ENCODED.startswith(param) or param in _POWERSHELL_ENCODED_ALIASES:
            return None, True
        if (_POWERSHELL_COMMAND.startswith(param) or param.startswith(_POWERSHELL_COMMAND)
                or param in _POWERSHELL_COMMAND_ALIASES):  # fmt: skip
            return " ".join(rest[index + 1 :]), False
        if _POWERSHELL_FILE.startswith(param):
            return None, False
    return None, False


def _moved(rest: Sequence[str], here: str | None) -> str | None:
    """Where cd, Set-Location or `git -C` leaves the shell: its first operand resolved against
    `here`, or None (unknown, judged as inside) for none, `-`, a variable or a path that cannot
    be placed."""
    target = next((word for word in rest if not word.startswith("-")), None)
    if target is None or _UNPLACED.search(target):
        return None
    try:
        return candidates(target, here or "")[0]
    except HookError:
        return None


def _guarded(word: str, here: str | None, live: tuple[str, ...]) -> bool:
    """Whether the file `word` names (relative to `here`) may lie under a live drive's checkout:
    a null device never does, a path the hook cannot place always may."""
    if word.casefold() in _NULL_DEVICES:
        return False
    if _UNPLACED.search(word):
        return True
    try:
        paths = candidates(word, here or "")
    except HookError:
        return True
    return any(_inside(path, live) is not None for path in paths)


def _guarded_dir(here: str | None, live: tuple[str, ...]) -> bool:
    return here is None or _inside(here, live) is not None


# --- the matching-session layer (D-17, D-18, D-44, D-45, DI-07) ------------------------------


def _claim(env: Mapping[str, str]) -> str | None:
    claim = env.get(CLAIM_ENV)
    return claim if isinstance(claim, str) and _CLAIM.fullmatch(claim) else None


def forms_for(kind: str) -> tuple[tuple[str, ...], ...]:
    """The wrapper forms a session of `kind` may run: MATCHING_FORMS for a matching session,
    ATTEMPT_FORMS for any other (D-26: readability gets no new form)."""
    return MATCHING_FORMS if kind == SESSION_KINDS[0] else ATTEMPT_FORMS


def attempt_form_matches(
    argv: Sequence[str], forms: Sequence[tuple[str, ...]] = ATTEMPT_FORMS
) -> bool:
    """Whether `argv` (the arguments after ATTEMPT_PREFIX) is exactly one of `forms`: the same
    length, the same tokens, and a name matching ATTEMPT_NAME where the form holds
    ATTEMPT_NAME_SLOT. Shared with the attempt wrapper (06-15)."""
    args = tuple(argv)
    return any(len(form) == len(args) and all(map(_token_matches, form, args, strict=True))
               for form in forms)  # fmt: skip


def _token_matches(expected: str, given: str) -> bool:
    if expected == ATTEMPT_NAME_SLOT:
        return ATTEMPT_NAME.fullmatch(given) is not None
    return expected == given


def bash_allowed(command: object, *, kind: str = SESSION_KINDS[0]) -> bool:
    """Whether a session of `kind` may run `command`: only the characters of the wrapper forms
    (so no shell metacharacter, quote, newline or tab can reach a shell), and its split argv
    is ATTEMPT_PREFIX followed by one of `forms_for(kind)` (D-44, D-26)."""
    if not isinstance(command, str) or not _BASH_CHARS.fullmatch(command):
        return False
    argv = shlex.split(command)
    prefix = len(ATTEMPT_PREFIX)
    forms = forms_for(kind)
    return tuple(argv[:prefix]) == ATTEMPT_PREFIX and attempt_form_matches(argv[prefix:], forms)


def _fold(rel: str) -> str:
    return rel.replace("\\", "/").casefold()


def _session_file_beside(rel: str, notes: str) -> bool:
    """Whether folded `rel` is one of SESSION_FILE_NAMES in the directory of the folded notes.md
    `notes` (07.2-02, 07.2-03, D-26): that exact path, at the build/driver/ shape."""
    beside = posixpath.dirname(notes) == posixpath.dirname(rel)
    return _is_notes(notes) and _is_session_file(rel) and beside


def matching_write_allowed(
    rel_path: str,
    *,
    claim: str | None,
    notes: str | None,
    tracked: Callable[[str], bool],
    unit_file: str | None = None,
    proposals: str | None = None,
    kind: str = SESSION_KINDS[0],
) -> bool:
    """The session write allowlist (D-17, D-24), one predicate for the hook and the driver's
    post-attempt audit; every path is repo-relative and compared casefolded. With a valid claim
    `<exe>/<unit>` and the view unit `unit_file` (at its shape, naming the claim): only that view
    unit, the attempt's notes.md under build/driver/ (`notes`), for a matching session (`kind`)
    the giveup.json, plan.json and check-note.json in the same directory as that notes.md
    (07.2-02, 07.2-03, D-26), and its
    proposals.jsonl under build/driver/ (`proposals`), never src/, include/ or
    config/<exe>/symbols.csv (D-19). No `unit_file`, nothing (07-13 removed the Phase 6
    allowlist of src/<exe>/<unit>.c and new include/*.h). `tracked` is kept for the callers'
    signature; no rule reads it any more."""
    if claim is None or not _CLAIM.fullmatch(claim) or unit_file is None:
        return False
    rel = _fold(rel_path)
    if notes is not None and rel == _fold(notes) and _is_notes(rel):
        return True
    if kind == SESSION_KINDS[0] and notes is not None and _session_file_beside(rel, _fold(notes)):
        return True
    if rel == _fold(unit_file) and _is_view_unit(rel, claim):
        return True
    return proposals is not None and rel == _fold(proposals) and _is_proposals(rel)


def _inside(path: str, root: tuple[str, ...]) -> str | None:
    """`path` relative to the checkout (any form of `root`; casefolded, forward slashes), or
    None outside it."""
    folded = path.casefold()
    for base in (form.casefold().rstrip("/") for form in root):
        if folded == base:
            return ""
        if folded.startswith(base + "/"):
            return folded[len(base) + 1 :]
    return None


def _session_root(payload: Mapping) -> tuple[str, ...]:
    """The checkout of the session's cwd (the cwd itself or its nearest ancestor with `.git`),
    as written and, when the host resolves it differently (a symlink, an 8.3 name), as real."""
    cwd = _cwd(payload)
    if not cwd:
        raise HookError("the payload has no cwd, so the session's checkout is unknown")
    start = Path(canonical(cwd))
    for directory in (start, *start.parents):
        if (directory / _GIT).exists():
            return tuple(candidates(directory.as_posix()))
    raise HookError(f"the session's cwd {cwd!r} is not inside a git checkout")


def _repo_relatives(raw: str, payload: Mapping, root: tuple[str, ...]) -> list[str] | None:
    """Every form of `raw` relative to the session's checkout, or None when one is outside it
    or the raw path names a home directory (`~`), which the hook cannot expand."""
    if raw.startswith("~"):
        return None
    rels = [_inside(path, root) for path in candidates(raw, _cwd(payload))]
    return None if any(rel is None for rel in rels) else rels


def _secret(rel: str) -> bool:
    return any(part.startswith(_SECRET_PREFIX) for part in rel.split("/"))


def _segments(text: str) -> list[str]:
    return [part.casefold() for part in text.replace("\\", "/").split("/") if part not in ("", ".")]


def _fits(name: str, segment: str) -> bool:
    """Whether a path segment `segment` (a glob segment or a plain name) can match `name`."""
    return fnmatch.fnmatchcase(name, segment)


def _wild(segment: str) -> bool:
    return any(char in segment for char in "*?[")


_PLAIN_GLOB = re.compile(r"[a-z0-9._*?-]*")  # a casefolded segment fnmatch models exactly


def _glob_segment(segment: str) -> str:
    """A Glob pattern or Grep glob segment as the egress rule judges it. fnmatch does not model
    extglob (`@( )`, `+( )`, `!( )`), alternation, negation or the like, so a segment holding
    anything but letters, digits, `._-` and the plain wildcards `*` and `?` fails closed as
    `**`: it can stand for any run of segments (security review, MEDIUM)."""
    return segment if _PLAIN_GLOB.fullmatch(segment) else "**"


_WORKTREE_LEAD = (".claude", "worktrees", "*")  # the segments before a worktree's checkout


def _leads_to_worktree(segs: Sequence[str]) -> bool:
    """Whether `segs` (at most three) can be the start of `.claude/worktrees/<name>`: each one
    fits its place, or is a glob that can match it."""
    return len(segs) <= len(_WORKTREE_LEAD) and all(
        _fits(s, want) or _fits(want, s) for want, s in zip(_WORKTREE_LEAD, segs, strict=False))


def _root_positions(segs: Sequence[str]) -> set[int]:
    """The indexes where a checkout root's top level can sit in `segs`: 0 (the session's own),
    and 3 when the first two can be `.claude/worktrees` (a worktree's checkout)."""
    roots = {0}
    if len(segs) > 2 and _fits(".claude", segs[0]) and _fits("worktrees", segs[1]):
        roots.add(3)
    return roots


def _reaches_egress_dir(segs: Sequence[str]) -> bool:
    """07.2-12 (D-10, the security review): whether a path or glob of these repo-relative
    segments can name or enter orig/ or third_party/ of this checkout or of a worktree in it.
    A plain segment naming either directory at any depth does; so does a wildcard segment that
    fits either one where a checkout's top level can sit; and so does a `**` before that point
    (it can stand for the segments leading there). Over-refusal is the safe side."""
    roots = _root_positions(segs)
    for i, seg in enumerate(segs):
        fits = any(_fits(name, seg) for name in _EGRESS_DENIED)
        if fits and (not _wild(seg) or i in roots):
            return True
        if "**" in seg and _leads_to_worktree(segs[:i]):
            return True
    return False


def _at_root(segs: Sequence[str]) -> bool:
    """Whether a directory of these segments holds a checkout's top level below it: the
    session's root, `.claude`, `.claude/worktrees` or one worktree's checkout."""
    return _leads_to_worktree(segs)


def _egress_forms(raw: str, payload: Mapping, root: tuple[str, ...],
                  env: Mapping[str, str]) -> set[str]:  # fmt: skip
    """Every repo-relative form of `raw` the hook can name: against the session's checkout and,
    as the always-on layer judges paths, against the project root and every `.git` anchor, each
    also with a worktree's prefix stripped (`_repo_forms`)."""
    forms = set()
    for path in candidates(raw, _cwd(payload)):
        inside = _inside(path, root)
        forms.update(() if inside is None else (inside,))
        forms.update(_repo_forms(path, (*root, *project_roots(env))))
    return forms


def _egress_problem(raw: str, payload: Mapping, root: tuple[str, ...],
                    env: Mapping[str, str]) -> str:  # fmt: skip
    """07.2-12 (D-10): why an egress session's read can reach orig/ or third_party/, or ''.
    Every form of the path is judged (`_egress_forms`). A Grep from a directory that holds a
    checkout's top level is refused whatever its glob (a ripgrep glob without a slash matches
    at any depth); a Glob pattern is judged joined to each form of its base, as written and in
    every brace expansion, and a pattern without a slash as one that may match at any depth.
    gitignore is never relied on."""
    tool, tool_input = payload["tool_name"], payload["tool_input"]
    forms = [_segments(form) for form in _egress_forms(raw, payload, root, env)]
    if any(_reaches_egress_dir(segs) for segs in forms):
        return "names orig/ or third_party/"
    if tool == "Grep" and any(_at_root(segs) for segs in forms):
        return "searches a directory that holds orig/ or third_party/"
    patterns = [tool_input.get(key) for key in ("pattern", "glob") if tool == "Glob"]
    patterns += [tool_input.get("glob")] if tool == "Grep" else []
    for pattern in (p for p in patterns if isinstance(p, str)):
        for text in _brace_expansions(pattern) or [pattern]:
            tail = [_glob_segment(seg) for seg in _segments(text)]
            tail = tail if "/" in text.replace("\\", "/") else ["**", *tail]
            if any(_reaches_egress_dir([*segs, *tail]) for segs in forms):
                return f"has a pattern {pattern!r} that can reach orig/ or third_party/"
    return ""


def _read(payload: Mapping, root: tuple[str, ...], env: Mapping[str, str]) -> Decision:
    """Read, Glob and Grep: inside the session's checkout and never a .env* file; in an egress
    session (EGRESS_ENV "1", 07.2-12) nothing under orig/ or third_party/ either."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, Mapping):
        raise HookError("the payload has no tool_input object")
    tool = payload["tool_name"]
    raw = tool_input.get("file_path") if tool == "Read" else tool_input.get("path")
    if raw is None and tool != "Read":
        raw = _cwd(payload)
    if not isinstance(raw, str):
        return _deny(f"{tool} without a path string is not allowed in a matching session")
    rels = _repo_relatives(raw, payload, root)
    if rels is None:
        return _deny(f"{tool} outside the repository is not allowed in a matching session")
    if any(_secret(rel) for rel in rels):
        return _deny(f"{tool} of a .env file is not allowed in a matching session")
    for key in ("pattern", "glob") if tool == "Glob" else ("glob",):
        problem = _pattern_problem(tool_input.get(key))
        if problem:
            return _deny(f"{tool} {key} {problem} is not allowed in a matching session")
    problem = _egress_problem(raw, payload, root, env) if env.get(EGRESS_ENV) == "1" else ""
    if problem:
        return _deny(f"{tool} that {problem} is not allowed in a session whose model is not "
                     "Anthropic's: the game files and the compiler never leave the machine "
                     "(D-10, docs/legal.md)")  # fmt: skip
    return NO_OPINION


def _pattern_problem(pattern: object) -> str:
    """Why a Glob pattern or Grep glob could leave the checkout or name a .env file, or ''. A
    character class is refused. Braces must be one level of plain {a,b} alternatives
    (_brace_expansions); the pattern as written and every expansion are judged, so the call is
    safe whether or not the tool expands braces."""
    if pattern is None:
        return ""
    if not isinstance(pattern, str):
        return "that is not a string"
    if any(char in pattern for char in _GLOB_CLASSES):
        return f"{pattern!r}, which holds a character class,"
    expansions = _brace_expansions(pattern)
    if expansions is None:
        return f"{pattern!r}, whose braces are not plain {{a,b}} alternatives,"
    for text in (pattern, *expansions):
        problem = _expansion_problem(text)
        if problem:
            return f"{pattern!r}{problem}"
    return ""


def _expansion_problem(text: str) -> str:
    """The leave-repo and .env rules for one pattern text, as the wording that follows it."""
    parts = text.replace("\\", "/").split("/")
    if text.startswith(("/", "\\", "~")) or _DRIVE.match(text) or ".." in parts:
        return ", which can leave the repository,"
    if any(part.casefold().startswith(_SECRET_PREFIX) for part in parts):
        return ", which names a .env file,"
    return ""


def _brace_group(inside: str) -> tuple[str, ...] | None:
    """The alternatives of one group, or None unless there are two or more, none empty, and no
    `..` (a range such as {a..c}, or a `..` component)."""
    alternatives = tuple(inside.split(","))
    if len(alternatives) < 2 or "" in alternatives or ".." in inside:
        return None
    return alternatives


def _brace_parts(pattern: str) -> list[tuple[str, ...]] | None:
    """The pattern as literal runs (1-tuples) and groups (their alternatives), or None for any
    other shape: a backslash (it could escape a brace past this hook), a nested group, a stray
    `}` or an unclosed `{`, or a group _brace_group refuses."""
    if "\\" in pattern:
        return None
    parts = []
    for index, token in enumerate(_BRACE_GROUP.split(pattern)):
        if index % 2 == 0:  # a literal run between groups: no brace may be left in it
            if "{" in token or "}" in token:
                return None
            parts.append((token,))
            continue
        group = _brace_group(token[1:-1])
        if group is None:
            return None
        parts.append(group)
    return parts


def _brace_expansions(pattern: str) -> list[str] | None:
    """Every text `pattern` spells: [pattern] with no brace, None for a refused brace shape or
    more than _MAX_BRACE_EXPANSIONS expansions (counted before expanding), else each choice of
    alternatives in order."""
    if "{" not in pattern and "}" not in pattern:
        return [pattern]
    parts = _brace_parts(pattern)
    if parts is None or math.prod(len(part) for part in parts) > _MAX_BRACE_EXPANSIONS:
        return None
    return ["".join(choice) for choice in itertools.product(*parts)]


def _matching_write(
    payload: Mapping, env: Mapping[str, str], tracked: Callable[[str], bool], root: tuple[str, ...]
) -> Decision:
    claim = _claim(env)
    if claim is None:
        return _deny(f"no valid {CLAIM_ENV}=<exe>/<unit>, so a matching session writes nothing")
    kind = env.get(SESSION_KIND_ENV, SESSION_KINDS[0])  # absent: a matching run
    if kind not in SESSION_KINDS:
        return _deny(f"{SESSION_KIND_ENV}={kind!r} is not one of {', '.join(SESSION_KINDS)}, "
                     "so the session writes nothing (D-18)")  # fmt: skip
    view = bool(env.get(UNIT_FILE_ENV))
    if kind == "readability" and not view:
        return _deny(f"a readability session writes only in view mode, and {UNIT_FILE_ENV} is "
                     "unset (D-18, D-24)")  # fmt: skip
    if not view:  # 07-13: no single-session allowlist is left to fall back to
        return _deny(f"a session needs the driver's {UNIT_FILE_ENV} (D-24), the private view "
                     "unit it edits, so without it the session writes nothing")  # fmt: skip
    raw, tool_input = _target(payload)
    rels = _repo_relatives(raw, payload, root)
    notes_rel = _session_relative(env, payload, root, NOTES_ENV)
    unit_rel = _session_relative(env, payload, root, UNIT_FILE_ENV)
    proposals_rel = _session_relative(env, payload, root, PROPOSALS_ENV)
    if unit_rel is None:  # set but unusable: never a looser allowlist
        return _deny(f"{UNIT_FILE_ENV} names no single path in the checkout, so the session "
                     "writes nothing (D-24)")  # fmt: skip
    paths = {"notes": notes_rel, "unit_file": unit_rel, "proposals": proposals_rel, "kind": kind}
    allowed = rels is not None and all(
        matching_write_allowed(rel, claim=claim, tracked=tracked, **paths) for rel in rels
    )
    if not allowed:
        return _deny(_view_denial(rels))
    if _under(rels[0], "src") or _under(rels[0], "include") or rels[0] == unit_rel:
        problem = _source_problem(payload["tool_name"], tool_input, canonical(raw, _cwd(payload)),
                                  asm_rule=_MATCHING_ASM_RULE, any_pragma_aux=True,
                                  any_pragma=True)  # fmt: skip
        if problem:
            return _deny(problem)
    return NO_OPINION


def _naming_state(rel: str) -> bool:
    """Whether repo-relative `rel` is shared naming state (D-19): a symbols.csv or include/."""
    return _SYMBOLS.fullmatch(rel) is not None or _under(rel, "include")


def _view_denial(rels: Sequence[str] | None) -> str:
    """The deny reason for a write outside a view-mode session's allowlist, by path."""
    if rels is not None and any(map(_naming_state, rels)):
        return ("the driver is the only writer of shared naming state (D-19); write a proposal "
                "to proposals.jsonl instead")  # fmt: skip
    return ("a session writes only its view unit, notes.md and proposals.jsonl (D-24), and a "
            "matching session also the giveup.json beside its notes.md (D-26)")  # fmt: skip


def _session_relative(
    env: Mapping[str, str], payload: Mapping, root: tuple[str, ...], name: str
) -> str | None:
    """The one repo-relative form (casefolded) of the driver's path in env `name`, or None when
    it is unset, unusable, outside the checkout or has more than one form."""
    raw = env.get(name, "")
    if not raw:
        return None
    try:
        rels = _repo_relatives(raw, payload, root)
    except HookError:
        return None
    return rels[0] if rels and len(set(rels)) == 1 else None


def _backgrounded(tool_input: object) -> bool:
    """M14(a): whether a Bash call asks for run_in_background; any value but absent or false
    counts (fail closed)."""
    value = tool_input.get("run_in_background") if isinstance(tool_input, Mapping) else None
    return value is not None and value is not False


def _short_check(command: str, tool_input: Mapping) -> bool:
    """Review WR-04: whether an allowed wrapper `command` is an `attempt check` (plain or
    --sweep) whose Bash timeout is missing, not a number, or below CHECK_TIMEOUT_MS."""
    if shlex.split(command)[len(ATTEMPT_PREFIX)] != "check":
        return False
    timeout = tool_input.get("timeout")
    number = isinstance(timeout, (int, float)) and not isinstance(timeout, bool)
    return not (number and timeout >= CHECK_TIMEOUT_MS)


def _matching(payload: Mapping, env: Mapping[str, str], tracked: Callable[[str], bool]) -> Decision:
    """Deny by default (D-17): the always rules first, then Read/Glob/Grep inside the repo, the
    allowlisted writes, and Bash only as an exact attempt-wrapper form."""
    tool = payload.get("tool_name")
    if not isinstance(tool, str):
        raise HookError("the payload has no tool_name string")
    if tool not in _MATCHING_TOOLS:
        return _deny(f"{tool} is not available in a matching session (D-17, D-45)")
    root = _session_root(payload)
    if tool in _READ_TOOLS:
        return _read(payload, root, env)
    if tool == "Bash":
        if _claim(env) is None:
            return _deny(f"no valid {CLAIM_ENV}=<exe>/<unit>, so a matching session runs nothing")
        tool_input = payload.get("tool_input")
        command = tool_input.get("command") if isinstance(tool_input, Mapping) else None
        kind = env.get(SESSION_KIND_ENV, SESSION_KINDS[0])  # absent: a matching run
        if not bash_allowed(command, kind=kind):
            forms = ", ".join(" ".join((*ATTEMPT_PREFIX, *form)) for form in forms_for(kind))
            return _deny(f"a matching session runs only the attempt wrapper: {forms} (D-44)")
        if _backgrounded(tool_input):
            return _deny("checks run in the foreground, one at a time: no run_in_background "
                         "in a matching session (M14)")  # fmt: skip
        if _short_check(command, tool_input):
            return CHECK_TIMEOUT_DENIAL
        return NO_OPINION
    decision = _always(payload, env)
    return decision if decision.deny else _matching_write(payload, env, tracked, root)


# --- the entry point -------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m reverseapoc.hooks")
    sub = parser.add_subparsers(dest="event", required=True)
    pre = sub.add_parser("pre-tool-use", help="decide one PreToolUse payload read from stdin")
    pre.add_argument("--layer", choices=LAYERS, required=True)
    return parser


def _git_tracked(cwd: str) -> Callable[[str], bool]:
    """main's `tracked`: whether git tracks repo-relative `rel` in the checkout holding `cwd`,
    compared casefolded as NTFS opens it. Any failure to ask git blocks the call."""

    def tracked(rel: str) -> bool:
        import subprocess  # only a matching-session header write needs git

        folded = rel.replace("\\", "/").casefold()
        spec = f":(top,icase){posixpath.dirname(folded) or '.'}"
        done = subprocess.run(
            ["git", "-C", cwd, "ls-files", "-z", "--full-name", "--", spec],
            capture_output=True, timeout=_GIT_TIMEOUT, check=False,
        )  # fmt: skip
        if done.returncode != 0:
            why = done.stderr.decode("utf-8", "replace").strip()
            raise HookError(f"git ls-files failed in {cwd!r}: {why}")
        names = done.stdout.decode("utf-8", "surrogateescape").split("\0")
        return folded in {name.casefold() for name in names if name}

    return tracked


def _run(argv: list[str] | None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HookError(f"the payload is not UTF-8 JSON: {exc}") from None
    cwd = payload.get("cwd", "") if isinstance(payload, dict) else ""
    decision = decide(payload, layer=args.layer, env=os.environ, tracked=_git_tracked(cwd))
    if decision.deny:
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": "deny",
                                      "permissionDecisionReason": decision.reason}}  # fmt: skip
        sys.stdout.buffer.write(json.dumps(out, separators=(",", ":")).encode("utf-8"))
        sys.stdout.buffer.flush()
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Exit 0 (deny JSON on stdout, or nothing) or 2 (the reason on stderr): any error, an
    unreadable payload included, blocks the call (D-15)."""
    try:
        return _run(argv)
    except BaseException as exc:  # fail closed on everything, SystemExit included
        try:
            sys.stderr.write(f"reverseapoc hooks: blocked: {type(exc).__name__}: {exc}\n")
        except BaseException:  # the block must survive a broken stderr
            pass
        return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(main())

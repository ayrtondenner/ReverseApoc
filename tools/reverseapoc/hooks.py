# SPDX-License-Identifier: GPL-3.0-or-later
"""Claude Code PreToolUse guardrail hooks (AGT-05, D-15..D-18, D-44..D-46, DI-07).

Run as `uv run --frozen python -I -m reverseapoc.hooks pre-tool-use --layer always|matching`
with the hook payload on stdin. Two layers:

- **always** (`.claude/settings.json`, every session in the repo, matcher
  `Edit|Write|MultiEdit|NotebookEdit`): blocks edits of the oracle's inputs and generated trees
  (D-16). Every other path stays editable, so GSD executors and the owner keep working on tools/,
  tests/, configure.py, docs/ and .planning/.

`decide` is the pure decision; `main` reads stdin, prints the deny JSON and exits 0, or prints
nothing and exits 0 for no opinion (never an allow decision, so Claude Code's own permission rules
still bind). Any error exits 2 with the reason on stderr, which blocks the call (fail closed);
Claude Code treats every other exit code as non-blocking, so main never returns one.

Paths are normalised before any rule: Windows (backslash or drive letter) and POSIX forms, `..`
resolved, compared casefolded (NTFS is case-insensitive). The checkout is the nearest ancestor
holding `.git` (a directory, or the file of a git worktree), so a worktree under
.claude/worktrees/ is judged as its own checkout."""

from __future__ import annotations

import argparse
import json
import ntpath
import os
import posixpath
import re
import sys
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

EXIT_OK = 0
EXIT_BLOCK = 2  # the only exit code besides 0 that Claude Code treats as blocking
LAYER_ALWAYS = "always"
LAYER_MATCHING = "matching"
LAYERS = (LAYER_ALWAYS, LAYER_MATCHING)
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
_PATH_FIELD = {"Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path",
               "NotebookEdit": "notebook_path"}  # fmt: skip

# D-16: the always-on layer's protected trees, repo-relative and casefolded.
_PROTECTED_DIRS = {
    "orig": "orig/ holds the original game files the oracle compares against",
}

_DRIVE = re.compile(r"[A-Za-z]:")
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


# --- paths -----------------------------------------------------------------------------------


def _is_windows(raw: str) -> bool:
    return "\\" in raw or _DRIVE.match(raw) is not None or raw.startswith("//?/")


def _strip_device_prefix(raw: str) -> str:
    """`\\\\?\\C:\\x` -> `C:\\x` and `\\\\?\\UNC\\server\\share` -> `\\\\server\\share`."""
    text = raw.replace("/", "\\")
    for prefix in ("\\\\?\\", "\\\\.\\"):
        if text.startswith(prefix):
            rest = text[len(prefix) :]
            return "\\\\" + rest[4:] if rest[:4].upper() == "UNC\\" else rest
    return raw


def _windows_components(path: str) -> str:
    """`path` (normalised, backslashes) with each component as NTFS opens it: an alternate data
    stream suffix (`name:stream`) dropped and trailing dots and spaces stripped."""
    drive, rest = ntpath.splitdrive(path)
    parts = [part.split(":")[0].rstrip(". ") for part in rest.split("\\")]
    return drive + "\\".join(parts)


def canonical(raw: str, cwd: str = "") -> str:
    """`raw` as an absolute, normalised path with forward slashes (case kept)."""
    if not isinstance(raw, str) or not raw or "\0" in raw:
        raise HookError(f"path {raw!r} is not a usable path")
    if _is_windows(raw) or (not raw.startswith("/") and _is_windows(cwd)):
        path = _strip_device_prefix(raw)
        if not ntpath.isabs(path):
            path = ntpath.join(_require_cwd(cwd, raw), path)
        path = ntpath.normpath(_windows_components(ntpath.normpath(path)))
        return path.replace("\\", "/")
    path = raw if raw.startswith("/") else posixpath.join(_require_cwd(cwd, raw), raw)
    return posixpath.normpath(path)


def _require_cwd(cwd: str, raw: str) -> str:
    if not cwd:
        raise HookError(f"path {raw!r} is relative and the payload has no cwd")
    return _strip_device_prefix(cwd)


def candidates(raw: str, cwd: str = "") -> list[str]:
    """The canonical path and, when it differs, the real one (symlinks and 8.3 names resolved by
    the host). A rule that denies either form denies the call."""
    lexical = canonical(raw, cwd)
    found = [lexical]
    if _is_windows(lexical) == (os.name == "nt"):  # the host can resolve only its own form
        real = os.path.realpath(lexical).replace("\\", "/")
        if real.casefold() != lexical.casefold():
            found.append(real)
    return found


def _root_of(path: str) -> Path | None:
    """The nearest proper ancestor of `path` holding `.git` (a checkout or worktree root); None
    for a path this host cannot place (the other platform's form)."""
    if not Path(path).is_absolute():
        return None
    for parent in Path(path).parents:
        if (parent / _GIT).exists():
            return parent
    return None


def _relative(path: str, root: Path) -> str:
    return Path(path).relative_to(root).as_posix().casefold()


def _repo_forms(path: str) -> Iterator[str]:
    """The casefolded repo-relative forms of `path`: relative to its checkout and, for a path
    under .claude/worktrees/<name>/, relative to that worktree too (even one whose `.git` is
    missing), so a worktree's orig/ is still orig/."""
    root = _root_of(path)
    if root is None:
        return
    rel = _relative(path, root)
    yield rel
    inner = _WORKTREE.fullmatch(rel)
    if inner is not None:
        yield inner.group(1)


def _under(rel: str, directory: str) -> bool:
    return rel == directory or rel.startswith(directory + "/")


# --- the always-on layer (D-16, D-46) --------------------------------------------------------


def _protected(rel: str) -> str | None:
    """Why the always layer refuses an edit of repo-relative `rel`, or None."""
    for directory, why in _PROTECTED_DIRS.items():
        if _under(rel, directory):
            return f"{directory}/ is protected for every session (D-16): {why}"
    return None


def _target(payload: Mapping) -> tuple[str, Mapping]:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, Mapping):
        raise HookError("the payload has no tool_input object")
    field = _PATH_FIELD[payload["tool_name"]]
    raw = tool_input.get(field)
    if not isinstance(raw, str):
        raise HookError(f"{payload['tool_name']} payload has no {field} string")
    return raw, tool_input


def _always(payload: Mapping, env: Mapping[str, str]) -> Decision:
    if payload.get("tool_name") not in EDIT_TOOLS:
        return NO_OPINION
    raw, _ = _target(payload)
    cwd = payload.get("cwd") or ""
    for path in candidates(raw, cwd if isinstance(cwd, str) else ""):
        for rel in _repo_forms(path):
            reason = _protected(rel)
            if reason is not None:
                return _deny(reason)
    return NO_OPINION


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
    raise HookError(f"unknown layer {layer!r}")


# --- the entry point -------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m reverseapoc.hooks")
    sub = parser.add_subparsers(dest="event", required=True)
    pre = sub.add_parser("pre-tool-use", help="decide one PreToolUse payload read from stdin")
    pre.add_argument("--layer", choices=LAYERS, required=True)
    return parser


def _git_tracked(cwd: str) -> Callable[[str], bool]:
    def tracked(rel: str) -> bool:
        raise HookError(f"cannot tell whether {rel} is tracked in {cwd}")

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

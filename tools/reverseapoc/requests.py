# SPDX-License-Identifier: GPL-3.0-or-later
"""`reverseapoc requests` (todo agent-requests-collector): the tooling requests agents leave in
their notes, grouped, with counts and example paths, as input for tooling todos.

It walks build/driver/<RUN>/<exe>/<function>/attempt-N (flags._run_dirs and
flags._attempt_dirs, as `causes` does) and reads each attempt's notes.md (attempt.NOTES_FILE).
The skill asks for a "tooling request" in notes.md (watcom-decomp "the window"), and agents
write it as a list item or inline: `3. Tooling request: ...`, `- Tooling request (repeated):
...`, `Tooling request, repeated from attempt 2: ...`, `(tooling request: ...)`.

- A note is cut into blocks (a blank line, a list item or a heading starts one), and each block's
  lines are joined, so a request wrapped over lines, or a tag split over two, is read whole.
- A request is the text after a tag (`tooling request`, an optional parenthesised or
  comma-led qualifier, then a colon; `requests` and Markdown bold too) up to the end of its
  sentence (not at `e.g.`, `i.e.` or `vs.`), or to the `)` closing a parenthesis the tag
  opened. A tag with no colon names no request and is skipped.
- Requests are grouped by group_key: lower case, hex addresses and `func_` names folded to N
  (causes' rule for hex), cut at the first clause break. A group counts the notes files that
  raise it (a note repeating a request counts once), most first.

Nothing is compiled and nothing under orig/ is read: the report holds the agents' own words.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import causes, flags
from .attempt import NOTES_FILE

_BLOCK_START = re.compile(r"\s*(?:[-*+]|\d+[.)]|#+)\s")  # a list item or a heading
# `tooling request` or `requests`, bold or not, an optional qualifier, then a colon
_TAG = re.compile(r"\**tooling\s+requests?\b\**(?:\s*\([^)]*\))?(?:,[^:.]{0,60})?\s*:\**",
                  re.IGNORECASE)  # fmt: skip
_SENTENCE_END = re.compile(r"(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)\.(?:\s|$)")  # not e.g. i.e. vs.
_FUNC_NAME = re.compile(r"\bfunc_[0-9a-f]{8}\b")
_CLAUSE_BREAK = re.compile(r"[,;:(]|\s(?:so|would|because)\s")
EXAMPLE_PATHS = 3  # the paths a group shows


class RequestsError(ValueError):
    """A named run does not exist, or a notes file cannot be read."""


def _blocks(text: str) -> Iterator[str]:
    block: list[str] = []
    for line in text.splitlines():
        if (not line.strip() or _BLOCK_START.match(line)) and block:
            yield " ".join(block)
            block = []
        if line.strip():
            block.append(line.strip())
    if block:
        yield " ".join(block)


def _request(block: str, tag: re.Match, end: int) -> str:
    """The request after `tag`, up to `end` (the next tag), its sentence's end or the `)`
    closing a parenthesis right before the tag."""
    text = block[tag.end():end]
    if block[:tag.start()].rstrip().endswith("("):
        text = text.split(")", 1)[0]
    stop = _SENTENCE_END.search(text)
    if stop is not None:
        text = text[:stop.start()]
    return text.strip().rstrip(".").strip()


def extract(text: str) -> list[str]:
    """Every tooling request of a notes.md text, in order (see the module docstring)."""
    out = []
    for block in _blocks(text):
        tags = list(_TAG.finditer(block))
        if not tags:
            continue
        ends = [tag.start() for tag in tags[1:]] + [len(block)]
        for tag, end in zip(tags, ends, strict=True):
            request = _request(block, tag, end)
            if request:
                out.append(request)
    return out


def group_key(request: str) -> str:
    """The request's group: lower case, `func_` names and hex folded to N, cut at the first
    clause break."""
    text = causes._hex_folded(_FUNC_NAME.sub("func_N", request.lower()))
    return _CLAUSE_BREAK.split(text, maxsplit=1)[0].strip().rstrip(".")


@dataclass(frozen=True)
class Group:
    key: str
    count: int  # the notes files that raise it
    example: str  # its first request as written
    paths: tuple[str, ...]  # up to EXAMPLE_PATHS notes files, repo-relative

    def to_json(self) -> dict:
        return {"request": self.key, "count": self.count, "example": self.example,
                "paths": list(self.paths)}  # fmt: skip


@dataclass(frozen=True)
class Requests:
    runs: int
    notes: int  # the notes files read
    lines: int  # the requests found
    groups: tuple[Group, ...]

    def to_json(self) -> dict:
        return {"runs": self.runs, "notes": self.notes, "lines": self.lines,
                "groups": [g.to_json() for g in self.groups]}  # fmt: skip

    def format(self) -> str:
        lines = [f"tooling requests: {self.lines} lines in {self.notes} notes files of "
                 f"{self.runs} runs, {len(self.groups)} groups (count: notes files raising it)"]
        for g in self.groups:
            lines += [f"  {g.count}  {g.key}", f"      e.g. {g.example}",
                      *(f"      in {path}" for path in g.paths)]  # fmt: skip
        return "\n".join(lines)


def _notes_files(repo: Path, runs: Sequence[str]) -> tuple[int, list[Path]]:
    try:
        run_dirs = flags._run_dirs(repo, runs)
    except flags.FlagsError as exc:
        raise RequestsError(str(exc)) from None
    notes = [attempt_dir / NOTES_FILE for run_dir in run_dirs
             for _, _, attempt_dir in flags._attempt_dirs(run_dir)
             if (attempt_dir / NOTES_FILE).is_file()]  # fmt: skip
    return len(run_dirs), notes


def collect(repo: Path, runs: Sequence[str] = ()) -> Requests:
    """The grouped requests of build/driver/<RUN> for each of `runs`, or of every run when
    none is named. An unknown run or an unreadable notes file is a RequestsError."""
    repo = Path(repo)
    run_count, notes = _notes_files(repo, runs)
    found: dict[str, list[tuple[str, str]]] = {}  # key -> (path, request), in walk order
    lines = 0
    for path in notes:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise RequestsError(f"cannot read {path}: {exc}") from None
        shown = path.relative_to(repo).as_posix()
        for request in extract(text):
            lines += 1
            found.setdefault(group_key(request), []).append((shown, request))
    groups = []
    for key, hits in found.items():
        paths = list(dict.fromkeys(path for path, _ in hits))
        groups.append(Group(key, len(paths), hits[0][1], tuple(paths[:EXAMPLE_PATHS])))
    groups.sort(key=lambda g: (-g.count, g.key))
    return Requests(run_count, len(notes), lines, tuple(groups))

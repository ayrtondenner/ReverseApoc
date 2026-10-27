"""The D-19 naming-proposal format: what a session writes to `<attempt dir>/proposals.jsonl`.

The driver is the only writer of shared naming state (D-19): the names in
`config/<exe>/symbols.csv` and the shared headers under `include/`. A session (its hooks allow
it only its view unit, notes.md and this file) asks for a change by appending one JSON object
per line:

- `{"op": "rename", "exe", "kind", "address", "name", "evidence"}`: give the func or data row
  at `address` (`0x%08X`) of `exe` (`ufo2p` or `tacp`) the C name `name`; the driver derives
  the linker name (unitdefs.c_name_of's rule run backwards);
- `{"op": "header", "path", "text", "evidence"}`: the whole text of one shared header
  `include/<name>.h` (D-19's struct fields, enums and constants are written this way).

`evidence` is `<kind>: <text>`, kind one of EVIDENCE_KINDS, the kinds readlint's header rule
cites (D-21: game evidence first, OpenApoc vocabulary allowed, nothing copied).

parse_line and read_proposals check the shape only: exact key sets, string values, the op,
kind, exe and address forms and the evidence form. Whether a proposal may be applied
(name_problem, rename_problem, header_problem) is a separate question the driver's rename step
(07-34) asks under the gate lock, against the naming state of that moment.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .functions import ADDRESS_DIGITS, SYMBOL_KINDS

OP_RENAME, OP_HEADER = "rename", "header"
OPS = (OP_RENAME, OP_HEADER)
KINDS = SYMBOL_KINDS  # symbols.csv kinds: ("func", "data")
EXES = ("ufo2p", "tacp")  # config/<exe> stems, as the driver's records name them
EVIDENCE_KINDS = ("string", "table", "call", "vocab")
EVIDENCE_TEXT_MAX = 200  # characters of evidence text after `<kind>: `
_KEYS = {
    OP_RENAME: frozenset({"op", "exe", "kind", "address", "name", "evidence"}),
    OP_HEADER: frozenset({"op", "path", "text", "evidence"}),
}
_ADDRESS = re.compile(rf"0x[0-9A-F]{{{ADDRESS_DIGITS}}}")
_EVIDENCE = re.compile(r"([a-z]+): (.*)", re.DOTALL)
_PRINTABLE = re.compile(r"[\x20-\x7e]*")  # printable ASCII: no newline or control in a record
_HEX_BASE = 16
_LINE_BREAK = "\n"


class ProposalError(ValueError):
    """A proposals.jsonl line that is not one well-formed proposal; the message names the line."""


@dataclass(frozen=True)
class Rename:
    """Give the `kind` row at `address` of `exe` the C name `name`."""

    exe: str
    kind: str
    address: int
    name: str
    evidence: str


@dataclass(frozen=True)
class Header:
    """Write `text` as the whole of the shared header `path` (`include/<name>.h`)."""

    path: str
    text: str
    evidence: str


def _refuse_constant(token: str) -> object:
    raise ValueError(f"{token} is not JSON")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"key {key!r} appears twice")
        obj[key] = value
    return obj


def _load(text: str) -> object:
    """Strict JSON: no NaN or Infinity, no repeated key (the last one would silently win)."""
    return json.loads(text, object_pairs_hook=_unique_keys, parse_constant=_refuse_constant)


def evidence_problem(evidence: str) -> str | None:
    """Why `evidence` is not `<kind>: <text>` (kind in EVIDENCE_KINDS, text 1 to
    EVIDENCE_TEXT_MAX printable ASCII characters, not only spaces), or None."""
    found = _EVIDENCE.fullmatch(evidence)
    if found is None:
        return f"evidence {evidence!r} is not '<kind>: <text>'"
    kind, text = found.groups()
    if kind not in EVIDENCE_KINDS:
        return f"evidence kind {kind!r} is not one of {', '.join(EVIDENCE_KINDS)}"
    if not text.strip():
        return f"evidence {evidence!r} has no text"
    if len(text) > EVIDENCE_TEXT_MAX:
        return f"evidence text is {len(text)} characters, more than {EVIDENCE_TEXT_MAX}"
    if not _PRINTABLE.fullmatch(text):
        return "evidence text is not printable ASCII on one line"
    return None


def _shape_problem(obj: object) -> str | None:
    """Why the decoded line is not one proposal object of the format, or None."""
    if not isinstance(obj, dict):
        return f"a {type(obj).__name__}, not a JSON object"
    op = obj.get("op")
    if op not in OPS:
        return f"op {op!r} is not one of {', '.join(OPS)}"
    keys = set(obj)
    if keys != _KEYS[op]:
        missing, extra = sorted(_KEYS[op] - keys), sorted(keys - _KEYS[op])
        return f"a {op} proposal has exactly {sorted(_KEYS[op])} (missing {missing}, extra {extra})"
    loose = sorted(key for key, value in obj.items() if not isinstance(value, str))
    if loose:
        return f"{', '.join(loose)} must be strings"
    if op == OP_RENAME:
        return _rename_shape_problem(obj)
    return evidence_problem(obj["evidence"])


def _rename_shape_problem(obj: dict[str, str]) -> str | None:
    if obj["exe"] not in EXES:
        return f"exe {obj['exe']!r} is not one of {', '.join(EXES)}"
    if obj["kind"] not in KINDS:
        return f"kind {obj['kind']!r} is not one of {', '.join(KINDS)}"
    if not _ADDRESS.fullmatch(obj["address"]):
        return f"address {obj['address']!r} is not 0x%0{ADDRESS_DIGITS}X"
    return evidence_problem(obj["evidence"])


def parse_line(text: str, lineno: int) -> Rename | Header:
    """The proposal on line `lineno` (counted from 1) of a proposals.jsonl; ProposalError
    naming the line when `text` is not exactly one proposal of the format."""
    try:
        obj = _load(text)
    except ValueError as exc:
        raise ProposalError(f"line {lineno}: not one JSON value ({exc})") from None
    problem = _shape_problem(obj)
    if problem is not None:
        raise ProposalError(f"line {lineno}: {problem}")
    if obj["op"] == OP_RENAME:
        return Rename(obj["exe"], obj["kind"], int(obj["address"], _HEX_BASE), obj["name"],
                      obj["evidence"])  # fmt: skip
    return Header(obj["path"], obj["text"], obj["evidence"])


def _decode(data: bytes) -> str:
    """`data` as strict UTF-8; ProposalError naming the line of the first bad byte."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        lineno = data.count(_LINE_BREAK.encode(), 0, exc.start) + 1
        raise ProposalError(f"line {lineno}: not UTF-8 ({exc.reason})") from None


def read_proposals(path: Path) -> list[Rename | Header]:
    """Every proposal in the proposals.jsonl at `path`, in file order. A missing file, an empty
    one, and lines holding only whitespace are no proposals (a session that proposes nothing,
    DEC-02). ProposalError naming the first malformed line otherwise; a caller that wants every
    good line of a partly bad file calls parse_line per line."""
    path = Path(path)
    if not path.exists():
        return []
    text = _decode(path.read_bytes())
    lines = enumerate(text.split(_LINE_BREAK), start=1)  # only \n: U+2028 may sit in a string
    return [parse_line(line, lineno) for lineno, line in lines if line.strip()]


# ---- Task 2 interface skeleton (behaviour follows in GREEN) ----

HEADER_TEXT_MAX = 64 * 1024


def name_problem(name: str) -> str | None:
    return None


def rename_problem(rename, *, symbols, functions, runtime_names, src_names, data_ranges=()):
    return None


def header_problem(header: Header) -> str | None:
    return None

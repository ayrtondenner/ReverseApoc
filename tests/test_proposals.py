"""proposals: the D-19 naming-proposal format sessions write to <attempt dir>/proposals.jsonl.

One JSON object per line, a rename (`op` rename: exe, kind, address, name, evidence) or a
shared-header write (`op` header: path, text, evidence), with D-21 evidence `<kind>: <text>`.
The driver's rename step (07-34) applies only what this module parses and validates. Every
name, address and header here is made up."""

from __future__ import annotations

import json

import pytest

from reverseapoc import proposals
from reverseapoc.proposals import Header, ProposalError, Rename

RENAME = {"op": "rename", "exe": "ufo2p", "kind": "func", "address": "0x000A3980",
          "name": "SoundVolume", "evidence": "string: 0x0012EFAC"}  # fmt: skip
HEADER = {"op": "header", "path": "include/sound.h",
          "text": "typedef struct Voice {\n    int volume;\n} Voice;\n",
          "evidence": "table: 0x0012F000"}  # fmt: skip


def _line(obj: object) -> str:
    return json.dumps(obj)


def _write(tmp_path, *lines: str):
    path = tmp_path / "proposals.jsonl"
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def test_parse_rename_and_header(tmp_path):
    path = _write(tmp_path, _line(RENAME), _line(HEADER))
    assert proposals.read_proposals(path) == [
        Rename(exe="ufo2p", kind="func", address=0x000A3980, name="SoundVolume",
               evidence="string: 0x0012EFAC"),
        Header(path="include/sound.h", text=HEADER["text"], evidence="table: 0x0012F000"),
    ]  # fmt: skip


def test_parse_line_returns_one_typed_proposal():
    assert proposals.parse_line(_line({**RENAME, "kind": "data", "exe": "tacp"}), 1) == Rename(
        exe="tacp", kind="data", address=0x000A3980, name="SoundVolume",
        evidence="string: 0x0012EFAC")  # fmt: skip


BAD_LINES = {
    "not-json": "{op: rename}",
    "a-list": _line([RENAME]),
    "a-string": _line("rename"),
    "extra-key": _line({**RENAME, "unit": "u_000a3980"}),
    "missing-key": _line({k: v for k, v in RENAME.items() if k != "evidence"}),
    "header-with-rename-keys": _line({**HEADER, "name": "Voice"}),
    "op-delete": _line({**RENAME, "op": "delete"}),
    "op-missing-type": _line({**RENAME, "op": None}),
    "kind-label": _line({**RENAME, "kind": "label"}),
    "address-short-lower": _line({**RENAME, "address": "0xa3980"}),
    "address-lower-hex": _line({**RENAME, "address": "0x000a3980"}),
    "address-int": _line({**RENAME, "address": 0xA3980}),
    "exe-unknown": _line({**RENAME, "exe": "UFO2P.EXE"}),
    "name-not-string": _line({**RENAME, "name": 7}),
    "text-not-string": _line({**HEADER, "text": ["int x;"]}),
    "duplicate-key": _line(RENAME)[:-1] + ', "name": "Other"}',
    "nan": _line(RENAME)[:-1].replace('"SoundVolume"', "NaN") + "}",
}  # fmt: skip


@pytest.mark.parametrize("bad", BAD_LINES.values(), ids=BAD_LINES.keys())
def test_bad_lines_name_the_line(tmp_path, bad):
    path = _write(tmp_path, _line(RENAME), _line(HEADER), bad)
    with pytest.raises(ProposalError, match=r"line 3\b"):
        proposals.read_proposals(path)


def test_bad_line_number_counts_from_one():
    with pytest.raises(ProposalError, match=r"line 9\b"):
        proposals.parse_line(_line({**RENAME, "op": "delete"}), 9)


def test_not_utf8_names_the_line(tmp_path):
    path = tmp_path / "proposals.jsonl"
    path.write_bytes(_line(RENAME).encode() + b"\n" + b'{"op": "\xff"}\n')
    with pytest.raises(ProposalError, match=r"line 2\b"):
        proposals.read_proposals(path)


@pytest.mark.parametrize("content", ["", "\n", "\n  \n"], ids=["empty", "newline", "blank"])
def test_empty_file(tmp_path, content):
    """DEC-02 edge: a session that proposes nothing leaves an empty or no proposals.jsonl."""
    path = tmp_path / "proposals.jsonl"
    path.write_text(content, encoding="utf-8")
    assert proposals.read_proposals(path) == []


def test_missing_file(tmp_path):
    assert proposals.read_proposals(tmp_path / "proposals.jsonl") == []


def test_crlf_lines_parse(tmp_path):
    path = tmp_path / "proposals.jsonl"
    path.write_bytes(f"{_line(RENAME)}\r\n{_line(HEADER)}\r\n".encode())
    assert [type(p) for p in proposals.read_proposals(path)] == [Rename, Header]


@pytest.mark.parametrize("evidence", [
    "string: 0x0012EFAC",
    "table: 0x0012F000 row 3 is the volume",
    "call: called by every sound effect player",
    "vocab: OpenApoc's Organisation",
    "call: " + "x" * 200,
])  # fmt: skip
def test_evidence_kinds_accepted(evidence):
    assert proposals.parse_line(_line({**RENAME, "evidence": evidence}), 1).evidence == evidence


@pytest.mark.parametrize("evidence", [
    "wiki: page",
    "call:",
    "call: ",
    "call:   ",
    "string 0x0012EFAC",
    "String: 0x0012EFAC",
    "call: " + "x" * 201,
    "call: café",
    "call: two\nlines",
    "",
])  # fmt: skip
def test_evidence_kinds_refused(evidence):
    with pytest.raises(ProposalError, match=r"line 4\b.*evidence"):
        proposals.parse_line(_line({**RENAME, "evidence": evidence}), 4)


def test_evidence_kinds_are_readlints():
    """D-21: the same kinds readlint's header rule cites (RL03)."""
    assert proposals.EVIDENCE_KINDS == ("string", "table", "call", "vocab")
    assert proposals.OPS == ("rename", "header")
    assert proposals.KINDS == ("func", "data")

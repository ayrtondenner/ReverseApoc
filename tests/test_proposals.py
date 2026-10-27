"""proposals: the D-19 naming-proposal format sessions write to <attempt dir>/proposals.jsonl.

One JSON object per line, a rename (`op` rename: exe, kind, address, name, evidence) or a
shared-header write (`op` header: path, text, evidence), with D-21 evidence `<kind>: <text>`.
The driver's rename step (07-34) applies only what this module parses and validates. Every
name, address and header here is made up."""

from __future__ import annotations

import json

import pytest

from reverseapoc import proposals
from reverseapoc.functions import FunctionRow, SymbolRow
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
    "deep-nesting": "[" * 100_000,  # fix round 1 I1: json.loads raises RecursionError
    "too-long": _line({**HEADER, "text": "x" * (3 * 64 * 1024)}),
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


def test_size_caps():
    """Fix round 1: a line holds at most one 64 KiB header after JSON escaping, a file at most
    4 MiB."""
    assert proposals.PROPOSAL_LINE_MAX == 3 * proposals.HEADER_TEXT_MAX
    assert proposals.PROPOSALS_FILE_MAX == 4 * 1024 * 1024


def test_largest_header_line_parses():
    text = "\n" * proposals.HEADER_TEXT_MAX  # every character escaped to two
    assert proposals.parse_line(_line({**HEADER, "text": text}), 1).text == text


def test_file_over_the_cap_is_refused(tmp_path):
    path = tmp_path / "proposals.jsonl"
    line = _line(RENAME).encode() + b"\n"
    path.write_bytes(line * (proposals.PROPOSALS_FILE_MAX // len(line) + 1))
    with pytest.raises(ProposalError, match="more than 4 MiB"):
        proposals.read_proposals(path)


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


# ---- Task 2: may a proposal be applied? ----

UNIT = "u_00010010"
FOO = FunctionRow(0x10010, 0x10020, "func_00010010", "game", UNIT, "call")
MIXER = FunctionRow(0x10020, 0x10030, "func_00010020", "game", UNIT, "call")
EXIT = FunctionRow(0x10030, 0x10038, "exit_", "runtime", "rt_exit", "runtime")
THUNK = FunctionRow(0x10038, 0x10040, "func_00010038", "thunk", UNIT, "call")
TABLE = FunctionRow(0x10040, 0x10050, "D_00010040", "data-in-code", UNIT, "fixup")
FUNCTIONS = (FOO, MIXER, EXIT, THUNK, TABLE)
SYMBOLS = (
    SymbolRow(0x10020, "Mixer_", "func"),  # C Mixer
    SymbolRow(0x20000, "_g_volume", "data"),  # C g_volume
    SymbolRow(0x20010, "_tick_", "data"),  # C tick_, linker _tick_
)
RUNTIME_NAMES = frozenset({"exit_", "_nmalloc_"})
SRC_NAMES = {"Helper": "src/ufo2p/u_00010010.c"}
DATA_RANGES = ((0x20000, 0x30000),)


def _rename(name: str = "SoundVolume", *, kind: str = "func", address: int = FOO.start) -> Rename:
    return Rename("ufo2p", kind, address, name, "call: called by every sound effect")


def _problem(rename: Rename, **kwargs) -> str | None:
    kwargs.setdefault("data_ranges", DATA_RANGES)
    return proposals.rename_problem(rename, symbols=SYMBOLS, functions=FUNCTIONS,
                                    runtime_names=RUNTIME_NAMES, src_names=SRC_NAMES,
                                    **kwargs)  # fmt: skip


BAD_NAMES = {
    "2fast": "identifier",
    "": "identifier",
    "Sound-Volume": "identifier",
    "café": "identifier",
    "while": "keyword",
    "__far": "keyword",
    "_Packed": "keyword",
    "FUN_1234": "placeholder",
    "sub_00a1": "placeholder",
    "DAT_0012efac": "placeholder",
    "LAB_00a1": "placeholder",
    "PTR_00A1": "placeholder",
    "UNK_1": "placeholder",
    "func_000A3980": "placeholder",
    "D_0012EFAC": "placeholder",
    "N" * 64: "63",
    # fix round 1 S2: identifiers the asm/pragma ban and the reserved headers rely on
    "asm": "keyword",
    "cdecl": "keyword",
    "far": "keyword",
    "near": "keyword",
    "huge": "keyword",
    "interrupt": "keyword",
    "pascal": "keyword",
    "fortran": "keyword",
    "_asm": "keyword",
    "_Pragma": "reserved",
    "__pragma": "reserved",
    "__emit": "reserved",
    "INCLUDE_ASM": "reserved",
    "COMMON_H": "reserved",
    "WATCOM_COMPAT_H": "reserved",
    "_Volume": "reserved",
    "__volume": "reserved",
}  # fmt: skip


@pytest.mark.parametrize(("name", "why"), BAD_NAMES.items(),
                         ids=[name[:12] or "empty" for name in BAD_NAMES])  # fmt: skip
def test_name_problems(name, why):
    problem = proposals.name_problem(name)
    assert problem is not None and why in problem


@pytest.mark.parametrize("name", ["SoundVolume", "g_volume", "_x", "N" * 63, "func_000a3980x",
                                  "FUNCTION_TABLE", "D_volume"])  # fmt: skip
def test_name_passes(name):
    assert proposals.name_problem(name) is None


def test_placeholder_regex_is_readlints():
    """R5 (owner-confirmed): Ghidra's LAB_/PTR_/UNK_ count as placeholders, as in readlint RL01."""
    assert proposals.PLACEHOLDER.pattern == (
        r"(?:FUN|sub|DAT|LAB|PTR|UNK)_[0-9A-Fa-f]+|func_[0-9A-F]{8}|D_[0-9A-F]{8}"
    )


def test_rename_passes():
    assert _problem(_rename()) is None
    assert _problem(_rename("g_master", kind="data", address=0x20100)) is None
    assert _problem(_rename("Thunk", address=THUNK.start)) is None


def test_rename_carries_name_problems():
    assert "keyword" in _problem(_rename("while"))


USED = {
    "symbols-func": ("Mixer", "func", FOO.start, ("symbols.csv", "0x00010020")),
    "symbols-data": ("g_volume", "data", 0x20100, ("symbols.csv", "0x00020000")),
    "symbols-cross-kind": ("g_volume", "func", FOO.start, ("symbols.csv", "0x00020000")),
    "symbols-linker": ("_tick", "func", FOO.start, ("symbols.csv", "_tick_")),
    "runtime-linker": ("exit", "func", FOO.start, ("runtime", "exit_")),
    "runtime-data": ("nmalloc_", "data", 0x20100, ("runtime", "_nmalloc_")),
    "runtime-verbatim": ("exit_", "data", 0x20100, ("runtime", "exit_")),
    "src": ("Helper", "func", FOO.start, ("src/ufo2p/u_00010010.c",)),
}  # fmt: skip


@pytest.mark.parametrize(("name", "kind", "address", "where"), USED.values(), ids=USED.keys())
def test_rename_unique(name, kind, address, where):
    problem = _problem(_rename(name, kind=kind, address=address))
    assert problem is not None
    for part in where:
        assert part in problem


def test_rename_to_its_current_name_is_refused():
    problem = _problem(_rename("Mixer", address=MIXER.start))
    assert problem is not None and "already" in problem


TARGETS = {
    "func-runtime-row": ("func", EXIT.start),
    "func-data-in-code-row": ("func", TABLE.start),
    "func-not-a-start": ("func", FOO.start + 4),
    "func-no-row": ("func", 0x50000),
    "data-inside-a-function": ("data", FOO.start + 8),
    "data-data-in-code-row": ("data", TABLE.start),
    "data-outside-the-data-objects": ("data", 0x40000),
}  # fmt: skip


@pytest.mark.parametrize(("kind", "address"), TARGETS.values(), ids=TARGETS.keys())
def test_rename_target_kind(kind, address):
    problem = _problem(_rename(kind=kind, address=address))
    assert problem is not None and f"0x{address:08X}" in problem


def test_data_ranges_are_required():
    """Fix round 1 I2: no default that skips the data-object check (it would fail open)."""
    with pytest.raises(TypeError):
        proposals.rename_problem(_rename(), symbols=SYMBOLS, functions=FUNCTIONS,
                                 runtime_names=RUNTIME_NAMES, src_names=SRC_NAMES)  # fmt: skip


def test_data_rename_with_no_data_object_is_refused():
    problem = _problem(_rename(kind="data", address=0x40000), data_ranges=())
    assert problem is not None and "no data object" in problem


def test_reserved_macros_are_read_from_the_reserved_headers():
    names = proposals.reserved_macros()
    assert {"INCLUDE_ASM", "COMMON_H", "WATCOM_COMPAT_H", "__far", "_cdecl"} <= names


PLAIN = ('/* sound.h: voice table types */\n#include "common.h"\n\n'
         "typedef struct Voice {\n    int volume;\n} Voice;\n")  # fmt: skip


def _header(path: str = "include/sound.h", text: str = PLAIN) -> Header:
    return Header(path, text, "table: 0x0012F000")


def test_plain_header_passes():
    assert proposals.header_problem(_header()) is None


ALLOWED_HEADER = """/* sound.h: voice table types (a ## b and #x in a comment are text) */
#ifndef SOUND_H
#define SOUND_H
#include "common.h"

#define MAX_VOICES 8
#define VOICE_MASK ((u32)0xFFFFFFFFUL)
#define VOICE_NAME "voice#1"

typedef enum VoiceState { VOICE_IDLE, VOICE_PLAYING = 2 } VoiceState;
typedef struct Voice {
    u8 volume;
    VoiceState state;
} Voice;
union Sample { s16 word; u8 bytes[2]; };

void StopVoice(Voice *voice);

#endif /* SOUND_H */
"""


def test_header_allowed_forms_pass():
    """Fix round 1 S1: include guards, typedef/struct/union/enum, prototypes and object-like
    constant #defines pass."""
    assert proposals.header_problem(_header(text=ALLOWED_HEADER)) is None
    assert proposals.header_problem(_header(text=ALLOWED_HEADER.replace("\n", "\r\n"))) is None


def test_header_of_64_kib_passes():
    filler = "/* " + "x" * (proposals.HEADER_TEXT_MAX - 7) + " */\n"
    assert len(filler) == proposals.HEADER_TEXT_MAX
    assert proposals.header_problem(_header(text=filler)) is None


BAD_PATHS = ["include/common.h", "include/watcom_compat.h", "include/Common.h", "include/sub/x.h",
             "include/../x.h", "src/ufo2p/x.h", "include/x.c", "include\\x.h", "x.h",
             "/include/x.h", "include/.h",
             # fix round 1: DOS device names, which Windows opens as devices
             "include/con.h", "include/nul.h", "include/aux.h", "include/prn.h",
             "include/com1.h", "include/com9.h", "include/lpt1.h", "include/lpt9.h"]  # fmt: skip


@pytest.mark.parametrize("path", BAD_PATHS)
def test_header_path_problems(path):
    problem = proposals.header_problem(_header(path))
    assert problem is not None and path in problem


BAD_TEXTS = {
    "inline-asm": ("void f(void) { __asm { nop } }\n", "inline assembly"),
    "pragma-aux-code": ("#pragma aux f = 0x90\n", "#pragma"),
    "pragma-pack": ("#pragma pack(1)\n", "#pragma"),
    "pragma-operator": ('_Pragma("pack(1)")\n', "inline assembly"),
    "include-path": ('#include "../x.h"\n', "include"),
    "non-ascii": ("/* café */\n", "ASCII"),
    "65-kib": ("/* " + "x" * (65 * 1024) + " */\n", "64 KiB"),
    # fix round 1 S1: rebuilding a banned token or a reserved macro through the preprocessor
    "paste": ("#define P(a, b) a##b\nP(__a, sm) int 3\n", "operator"),
    "paste-spaced": ("#define P a ## b\n", "operator"),
    "paste-digraph": ("#define P a %:%: b\n", "%:"),
    "paste-trigraph": ("#define P a ??=??= b\n", "operator"),
    "paste-across-lines": ("#define P a #\\\n# b\n", "operator"),
    "stringize": ("#define S(x) #x\n", "operator"),
    "digraph-directive": ("%:define VOICES 8\n", "%:"),
    "function-like": ("#define MAX(a, b) ((a) > (b) ? (a) : (b))\n", "function-like"),
    "define-include-asm": ("#define INCLUDE_ASM 1\n", "reserved"),
    "undef-include-asm": ("#undef INCLUDE_ASM\n", "reserved"),
    "define-keyword-macro": ("#define __far __huge\n", "reserved"),
    "undef-keyword-macro": ("#  undef _cdecl\n", "reserved"),
    "define-common-guard": ("#define COMMON_H\n", "reserved"),
    "brace-body": ("#define BEGIN {\n", "constant"),
    "statement-body": ("#define STOP return;\n", "constant"),
    "nul": ("int x;\x00\n", "control"),
    "vertical-tab": ("int x;\x0b\n", "control"),
    "delete": ("int x;\x7f\n", "control"),
}  # fmt: skip


@pytest.mark.parametrize(("text", "why"), BAD_TEXTS.values(), ids=BAD_TEXTS.keys())
def test_header_problems(text, why):
    problem = proposals.header_problem(_header(text=text))
    assert problem is not None and why in problem

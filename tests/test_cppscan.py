"""The C vs C++ scan over synthetic EXEs (tests/cpptree.py): every byte is made up."""

from __future__ import annotations

import pytest

from conftest import fixup_record
from cpptree import XI_ROUTINES, YI_ROUTINES, inirt_row, init_exe, write_init_lib
from libtree import OBJ1_BASE, OBJ2_BASE
from reverseapoc import cppscan
from reverseapoc.cppscan import CppScanError, InitEntry, init_tables, scan
from reverseapoc.le import LE
from reverseapoc.libmatch import STATUS_AMBIGUOUS, STATUS_UNIQUE, MatchRange


@pytest.fixture
def watcom(tmp_path):
    write_init_lib(tmp_path / "w")
    return tmp_path / "w"


def test_init_tables_through_inirt386(watcom):
    xi, yi = init_tables(LE(init_exe()), [inirt_row()], watcom)
    assert xi == (
        InitEntry("XI", 0x20100, 0, 32, XI_ROUTINES[0], False),
        InitEntry("XI", 0x20106, 0, 1, XI_ROUTINES[1], True),
        InitEntry("XI", 0x2010C, 0, 32, XI_ROUTINES[2], False),
    )
    assert yi == (InitEntry("YI", 0x20112, 0, 32, YI_ROUTINES[0], False),)


def test_c_verdict(watcom):
    report = scan(LE(init_exe()), [inirt_row()], watcom, exe="SYNTH.EXE")
    assert report.verdict.startswith("C (wcc386)")
    assert report.exe == "SYNTH.EXE"


def test_program_priority_is_cpp_evidence(watcom):
    report = scan(LE(init_exe(xi=(32, 64, 32))), [inirt_row()], watcom, exe="SYNTH.EXE")
    assert not report.verdict.startswith("C (wcc386)")
    assert "XI priority 64" in report.verdict


def test_destructor_priority_is_cpp_evidence(watcom):
    report = scan(LE(init_exe(yi=(40,))), [inirt_row()], watcom, exe="SYNTH.EXE")
    assert "YI priority 40" in report.verdict


def test_bad_table_length(watcom):
    exe = init_exe(xi=(), yi=(), bounds=(0x20100, 0x20111, 0x20111, 0x20111))
    with pytest.raises(CppScanError, match="multiple of 6"):
        init_tables(LE(exe), [inirt_row()], watcom)


def test_table_outside_the_data_object(watcom):
    exe = init_exe(xi=(), yi=(), bounds=(0x10100, 0x10106, 0x10106, 0x10106))
    with pytest.raises(CppScanError, match="data object"):
        init_tables(LE(exe), [inirt_row()], watcom)


def test_missing_inirt386(watcom):
    with pytest.raises(CppScanError, match="inirt386"):
        init_tables(LE(init_exe()), [inirt_row(module="other")], watcom)


def test_missing_le_fixup_at_a_bound_site(watcom):
    """A row whose start does not line up with the planted code finds no LE fixup there."""
    with pytest.raises(CppScanError, match="no LE fixup"):
        init_tables(LE(init_exe()), [inirt_row(start=0x10301, end=0x10329)], watcom)


def test_library_path_must_stay_in_the_tree(watcom):
    with pytest.raises(CppScanError, match="outside"):
        init_tables(LE(init_exe()), [inirt_row(libraries=("../../CLIB3R.LIB",))], watcom)


def test_report_holds_counts_addresses_and_names_only(watcom):
    report = scan(LE(init_exe()), [inirt_row()], watcom, exe="SYNTH.EXE")
    text = report.format()
    assert "XI 0x00020100..0x00020112: 3 entries" in text
    assert "YI 0x00020112..0x00020118: 1 entries" in text
    data = report.to_json()
    assert data["verdict"] == report.verdict
    assert [e["priority"] for e in data["tables"]["XI"]["entries"]] == [32, 1, 32]


# ---- the remaining signals ----


def _row(
    module: str, libraries: tuple[str, ...], status: str = STATUS_UNIQUE, start: int = 0x10700
) -> MatchRange:
    return MatchRange(start, start + 0x20, "_TEXT", module, libraries, ("10.6",), (), status)


def test_cpp_only_modules():
    rows = [
        _row("cppmod", ("PLIB3R.LIB",), start=0x10700),
        _row("fatalerr", ("DOS/CLIB3R.LIB", "PLIB3R.LIB"), start=0x10720),  # C and C++ alike
        _row("undefmbr", ("PLIB3R.LIB",), STATUS_AMBIGUOUS, start=0x10740),  # Pitfall 4 stub
        _row("complex", ("PLBX3R.LIB", "CPLX3R.LIB"), start=0x10760),
        _row("printf", ("DOS/CLIB3R.LIB",), start=0x10780),
    ]
    assert cppscan.cpp_only_modules(rows) == ("complex", "cppmod")


def test_string_counts():
    exe = init_exe(extra_data={
        0x20150: b"__wcpp_x\x00__wcpp_y\x00",
        0x20170: b"W?abc$\x00W?\x00W?1",
        0x10700: b"__wcpp_ in the code object W?abc",
    })  # fmt: skip
    assert cppscan.string_counts(LE(exe)) == (2, 1)


def _off32_run(at: int, targets: list[int]) -> bytes:
    """Off32 LE fixups in object 2, 4 bytes apart from `at`, to these object 1 addresses."""
    return b"".join(fixup_record(7, at + 4 * k - OBJ2_BASE, 1, t - OBJ1_BASE)
                    for k, t in enumerate(targets))  # fmt: skip


VTABLE_RUN = _off32_run(0x20180, [0x10800, 0x10810, 0x10820])


def test_vtable_candidates():
    data_fixups = (
        VTABLE_RUN
        + _off32_run(0x201A0, [0x10300, 0x10304])  # targets inside the inirt386 row
        + _off32_run(0x201C0, [0x10900])  # a single pointer
        + b"".join(fixup_record(7, 0x1D0 + 4 * k, 2, 0x10) for k in range(2))  # to object 2
    )
    le = LE(init_exe(data_fixups=data_fixups))
    assert cppscan.vtable_candidates(le, [inirt_row()]) == 1


def test_vtables_never_decide(watcom):
    report = scan(LE(init_exe(data_fixups=VTABLE_RUN)), [inirt_row()], watcom, exe="SYNTH.EXE")
    assert report.vtable_candidates == 1
    assert report.verdict.startswith("C (wcc386)")
    assert "1 vtable-shaped candidate runs" in report.verdict


def test_cpp_verdict_names_modules(watcom):
    rows = [inirt_row(), _row("cppmod", ("PLIB3R.LIB",))]
    report = scan(LE(init_exe()), rows, watcom, exe="SYNTH.EXE")
    assert report.cpp_only_modules == ("cppmod",)
    assert report.verdict.startswith("C++ evidence:")
    assert "modules needing wpp386: cppmod" in report.verdict


def test_cpp_verdict_without_modules_says_so(watcom):
    exe = init_exe(extra_data={0x20150: b"__wcpp_x"})
    report = scan(LE(exe), [inirt_row()], watcom, exe="SYNTH.EXE")
    assert "__wcpp_ strings x1" in report.verdict
    assert "modules needing wpp386: not located (no C++-only runtime rows)" in report.verdict


def test_empty_tables(watcom):
    exe = init_exe(xi=(), yi=(), bounds=(0x20100,) * 4)
    report = scan(LE(exe), [inirt_row()], watcom, exe="SYNTH.EXE")
    assert (report.xi, report.yi) == ((), ())
    assert report.verdict.startswith("C (wcc386)")
    counts = (report.cpp_only_modules, report.wcpp_strings, report.mangled_strings,
              report.vtable_candidates)  # fmt: skip
    assert counts == ((), 0, 0, 0)


def test_format_lists_every_signal_count(watcom):
    report = scan(LE(init_exe(data_fixups=VTABLE_RUN)), [inirt_row()], watcom, exe="SYNTH.EXE")
    text = report.format()
    assert "C++-only runtime rows (CODE segments only; COMDAT code is not matched): none" in text
    assert "__wcpp_ strings 0, W? strings 0, vtable-shaped candidate runs 1" in text

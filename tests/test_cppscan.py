"""The C vs C++ scan over synthetic EXEs (tests/cpptree.py): every byte is made up."""

from __future__ import annotations

import pytest

from cpptree import XI_ROUTINES, YI_ROUTINES, inirt_row, init_exe, write_init_lib
from reverseapoc.cppscan import CppScanError, InitEntry, init_tables, scan
from reverseapoc.le import LE


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

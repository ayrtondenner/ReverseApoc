"""The C vs C++ scan over synthetic EXEs (tests/cpptree.py): every byte is made up."""

from __future__ import annotations

import pytest

import omfimage as om
from conftest import fixup_record
from cpptree import (
    CPP_LIBRARY,
    LIBRARY,
    XI_ROUTINES,
    YI_ROUTINES,
    inirt_row,
    init_exe,
    write_cpp_lib,
    write_init_lib,
)
from libtree import OBJ1_BASE, OBJ2_BASE, body, code_module, fake_module, write_lib
from reverseapoc import cppscan
from reverseapoc.cppscan import CppScanError, InitEntry, init_tables, scan
from reverseapoc.le import LE
from reverseapoc.libmatch import STATUS_AMBIGUOUS, STATUS_UNIQUE, MatchRange


@pytest.fixture
def watcom(tmp_path):
    """Watcom 10.6 with the inirt386 library and a readable C++ library: every signal computes."""
    write_init_lib(tmp_path / "w")
    write_cpp_lib(tmp_path / "w")
    return tmp_path / "w"


@pytest.fixture
def c_only_watcom(tmp_path):
    """Watcom 10.6 with the inirt386 library but no C++ library at all."""
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
    assert report.verdict.startswith("C (wcc386): ")
    assert report.cpp_only_gap == ""
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
    module: str,
    libraries: tuple[str, ...],
    status: str = STATUS_UNIQUE,
    start: int = 0x10700,
    versions: tuple[str, ...] = ("10.6",),
) -> MatchRange:
    return MatchRange(start, start + 0x20, "_TEXT", module, libraries, versions, (), status)


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
    assert report.verdict.startswith("C (wcc386): ")
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
    assert report.verdict.startswith("C (wcc386): ")
    counts = (report.cpp_only_modules, report.wcpp_strings, report.mangled_strings,
              report.vtable_candidates)  # fmt: skip
    assert counts == ((), 0, 0, 0)


def test_mangled_names_alone_are_cpp_evidence(watcom):
    """Dropping the `W?` count from the signals would make this EXE read as C."""
    exe = init_exe(extra_data={0x20150: b"W?abc$"})
    report = scan(LE(exe), [inirt_row()], watcom, exe="SYNTH.EXE")
    assert (report.wcpp_strings, report.mangled_strings) == (0, 1)
    assert report.verdict.startswith("C++ evidence:")
    assert "W? strings x1" in report.verdict


def test_format_lists_every_signal_count(watcom):
    report = scan(LE(init_exe(data_fixups=VTABLE_RUN)), [inirt_row()], watcom, exe="SYNTH.EXE")
    text = report.format()
    assert "C++-only runtime rows (CODE segments only; COMDAT code is not matched): none" in text
    assert "__wcpp_ strings 0, W? strings 0, vtable-shaped candidate runs 1" in text


# ---- the C++-only module signal needs C++ libraries to have been swept ----

NOT_COMPUTED = "C++-only runtime module signal was not computed"


def _assert_uncomputed(report, *words):
    """No C verdict claims the signal: the verdict, the gap, the text and the JSON say so."""
    assert not report.verdict.startswith("C (wcc386): ")
    assert report.verdict.startswith("C (wcc386) on partial evidence")
    assert NOT_COMPUTED in report.verdict
    assert "no C++-only runtime module" not in report.verdict
    for word in words:
        assert word in report.cpp_only_gap
        assert word in report.verdict
    lines = report.format().splitlines()
    assert any(line.startswith("C++-only runtime rows: not computed") for line in lines)
    assert not any(line.startswith("C++-only runtime rows") and line.endswith(": none")
                   for line in lines)  # fmt: skip
    data = report.to_json()
    assert data["cpp_only_modules_computed"] is False
    assert data["cpp_only_modules_gap"] == report.cpp_only_gap
    assert data["verdict"] == report.verdict


def test_no_cpp_library_leaves_the_module_signal_uncomputed(c_only_watcom):
    report = scan(LE(init_exe()), [inirt_row()], c_only_watcom, exe="SYNTH.EXE")
    assert report.cpp_only_modules == ()
    _assert_uncomputed(report, "10.6", "no C++ library")


def test_unreadable_cpp_library_leaves_the_module_signal_uncomputed(watcom):
    (watcom / "10.6" / "LIB386" / CPP_LIBRARY).write_bytes(b"not an OMF library")
    report = scan(LE(init_exe()), [inirt_row()], watcom, exe="SYNTH.EXE")
    _assert_uncomputed(report, "10.6", CPP_LIBRARY, "not OMF")


def test_a_cpp_library_with_an_unparsed_module_leaves_the_signal_uncomputed(watcom):
    """One module of the library is skipped by the sweep: a C++-only module could hide there."""
    bad = om.module("bad", om.lnames("", "_TEXT", "CODE"), om.segdef32(2, 3, 8),
                    om.pubdef32(5, [("h_", 0)]))  # fmt: skip
    write_lib(watcom, "10.6", CPP_LIBRARY, [code_module("cppmod", body(40)), bad])
    report = scan(LE(init_exe()), [inirt_row()], watcom, exe="SYNTH.EXE")
    _assert_uncomputed(report, "10.6", CPP_LIBRARY, "module 2")


def test_every_version_the_map_names_needs_cpp_libraries(watcom):
    """Rows naming 10.5 too, which holds the inirt386 library but no C++ one."""
    write_init_lib(watcom, "10.5")
    rows = [inirt_row(versions=("10.5", "10.6"))]
    report = scan(LE(init_exe()), rows, watcom, exe="SYNTH.EXE")
    _assert_uncomputed(report, "10.5")
    assert "10.6" not in report.cpp_only_gap


def test_a_named_version_without_a_lib_tree_leaves_the_signal_uncomputed(watcom):
    rows = [inirt_row(), _row("other", ("DOS/CLIB3R.LIB",), versions=("9.9",))]
    report = scan(LE(init_exe()), rows, watcom, exe="SYNTH.EXE")
    _assert_uncomputed(report, "9.9", "LIB386")


def test_cpp_evidence_without_cpp_libraries_does_not_claim_no_modules(c_only_watcom):
    report = scan(LE(init_exe(xi=(32, 64, 32))), [inirt_row()], c_only_watcom, exe="SYNTH.EXE")
    assert report.verdict.startswith("C++ evidence:")
    assert "XI priority 64" in report.verdict
    assert "modules needing wpp386: not located (C++-only runtime module signal" in report.verdict
    assert "not computed" in report.format()


def test_a_version_name_leaving_the_watcom_dir_is_refused(watcom):
    rows = [inirt_row(), _row("other", ("DOS/CLIB3R.LIB",), versions=("../..",))]
    with pytest.raises(CppScanError, match="bare directory name"):
        scan(LE(init_exe()), rows, watcom, exe="SYNTH.EXE")


def test_a_map_naming_no_version_leaves_the_signal_uncomputed(watcom):
    assert "no Watcom version" in cppscan.cpp_only_gap([], watcom)


# ---- the library and version the inirt386 segment is re-read from ----


def test_init_segment_skips_a_version_that_lacks_the_library(tmp_path):
    """The row's versions and libraries are independent sets: (10.5, library) is absent."""
    write_init_lib(tmp_path / "w", "10.6")
    xi, yi = init_tables(LE(init_exe()), [inirt_row(versions=("10.5", "10.6"))], tmp_path / "w")
    assert [e.priority for e in xi] == [32, 1, 32]
    assert [e.priority for e in yi] == [32]


def test_init_segment_skips_a_library_missing_from_the_version(tmp_path):
    write_init_lib(tmp_path / "w")
    row = inirt_row(libraries=("NT/CLIB3R.LIB", LIBRARY))
    xi, _yi = init_tables(LE(init_exe()), [row], tmp_path / "w")
    assert len(xi) == 3


def test_init_segment_takes_the_pair_that_holds_the_module(tmp_path):
    """10.5 has the library file but another module in it: the 10.6 copy is the one to read."""
    write_lib(tmp_path / "w", "10.5", LIBRARY, [fake_module()])
    write_init_lib(tmp_path / "w", "10.6")
    xi, _yi = init_tables(LE(init_exe()), [inirt_row(versions=("10.5", "10.6"))], tmp_path / "w")
    assert len(xi) == 3


def test_init_segment_refuses_when_no_pair_exists(tmp_path):
    (tmp_path / "w").mkdir()
    with pytest.raises(CppScanError, match="not found"):
        init_tables(LE(init_exe()), [inirt_row(versions=("10.5", "10.6"))], tmp_path / "w")


def test_init_segment_refuses_when_no_pair_holds_the_module(tmp_path):
    write_lib(tmp_path / "w", "10.6", LIBRARY, [fake_module()])
    with pytest.raises(CppScanError, match="no inirt386 CODE segment"):
        init_tables(LE(init_exe()), [inirt_row()], tmp_path / "w")

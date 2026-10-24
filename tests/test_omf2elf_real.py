"""Real-file test: probe/cg_basic.c compiled by Watcom 10.6 under the `*` rule converts to ELF with
every segment, public and fixup accounted for (SPL-07).

Skips without the installed 10.6 tree (REVERSEAPOC_WATCOM_DIR points a git worktree at the main
checkout's trees) or without a compiler runner (the Windows host, or wibo in the container). The
object, the ELF, the log and the gate stamps are written only under build/test-omf2elf/
(gitignored). Assertions compare the converted ELF with the OMF module read by omf.read_object;
no byte of a compiled file is written into this test.
"""

from __future__ import annotations

import json
import shutil
import struct

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_runner, requires_version
from elfread import read_elf
from reverseapoc.cli import main as cli_main
from reverseapoc.compiler import compile_source
from reverseapoc.omf import Module, read_object
from reverseapoc.omf2elf import convert_file, is_debug

OUT = REPO_ROOT / "build" / "test-omf2elf"
SOURCE = REPO_ROOT / "probe" / "cg_basic.c"
FIELD = struct.Struct("<i")
PC32_BIAS = -4  # i386 psABI: a PC32 addend counts from the end of the 4-byte field
R_386_32 = 1
R_386_PC32 = 2
STB_GLOBAL = 1


@pytest.fixture(scope="module")
def probe_object():
    """(object path, its OMF module): cg_basic.c compiled once for this module's tests."""
    requires_runner()
    requires_version("10.6")
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    obj = OUT / "cg_basic.obj"
    result = compile_source(SOURCE, obj, watcom_dir=WATCOM_DIR, log=OUT / "cc.log",
                            stamps=OUT / "stamps")  # fmt: skip
    assert result.ok, result.output
    return obj, read_object(obj.read_bytes())


def emitted(module: Module):
    return [seg for seg in module.segments if not is_debug(seg)]


def test_probe_object_converts(probe_object):
    obj, module = probe_object
    out = OUT / "cg_basic.o"
    convert_file(obj, out)
    elf = read_elf(out.read_bytes())
    segs = emitted(module)
    assert segs and segs[0].is_code
    sections = list(elf.sections[: len(segs)])  # the data sections come first, in SEGDEF order
    assert [s.name for s in sections] == [seg.name for seg in segs]
    index_of = {seg.index: sec.index for seg, sec in zip(segs, sections, strict=True)}

    publics = [p for p in module.publics if p.segment_index in index_of]
    assert publics
    for pub in publics:
        sym = elf.symbol(pub.name)
        assert (sym.bind, sym.section_index, sym.value) == (
            STB_GLOBAL, index_of[pub.segment_index], pub.offset
        )  # fmt: skip

    fixups = 0
    for seg in segs:
        relocs = {r.offset: r for r in elf.relocs(index_of[seg.index])}
        assert sorted(relocs) == sorted(fx.offset for fx in seg.fixups)
        for fx in seg.fixups:
            stored = FIELD.unpack_from(seg.data, fx.offset)[0]
            rel = relocs[fx.offset]
            if fx.segment_relative:
                assert (rel.type, rel.addend) == (R_386_32, stored + fx.displacement)
            else:
                assert (rel.type, rel.addend) == (R_386_PC32, stored + fx.displacement + PC32_BIAS)
            if fx.target_kind == "extern":
                assert rel.symbol == fx.target_name
            else:
                assert rel.symbol_section_index == index_of[fx.target_index]
        fixups += len(seg.fixups)
    assert fixups > 0


def test_probe_object_round_trips_through_the_cli(probe_object, capsys):
    obj, module = probe_object
    out = OUT / "cg_basic-cli.o"
    assert cli_main(["omf2elf", str(obj), "-o", str(out), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["relocations"] == sum(len(seg.fixups) for seg in emitted(module))
    assert report["sections"] == len(emitted(module))
    assert out.is_file()

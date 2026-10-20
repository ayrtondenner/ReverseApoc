"""Spike 001: walk every page-map entry and fixup record raw and check the LE facts.

Run: uv run python .planning/spikes/001-le-pages-and-fixups/check.py [ORIG_DIR]
Reads orig/ only, writes nothing, prints offsets, VAs, counts and booleans only.
Exit 1 when any claim fails.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

from rawle import KIND_NAME, RawFixup, RawLE, locate_by_forward_scan

from reverseapoc.le import LE

REPO = Path(__file__).resolve().parents[3]

# Provisional facts from 03-RESEARCH.md "Measured layout of the real files".
EXPECTED = {
    "UFO2P.EXE": {
        "pages": 303,
        "straddlers": [
            0x1EFFD, 0x28FFD, 0x36FFE, 0x62FFF, 0x67FFE, 0x6AFFE, 0x7FFFF,
            0x98FFF, 0x9FFFF, 0xA3FFE, 0xB0FFD, 0xB4FFF, 0xC6FFD, 0xC8FFF,
        ],
        "bss_cut": (0x13E27C, 3),
        "kinds": {"off32": 28183, "sel16": 10, "ptr16:32": 4, "rel32": 0},
    },
    "TACP.EXE": {
        "pages": 666,
        "straddlers": [
            0x39FFD, 0x3BFFF, 0x42FFD, 0x43FFE, 0x52FFD, 0x6DFFE, 0x89FFD,
            0x8AFFF, 0x9EFFD, 0xA8FFD, 0xB8FFD,
        ],
        "bss_cut": (0x2B6538, 3),
        "kinds": {"off32": 24424, "sel16": 10, "ptr16:32": 4, "rel32": 0},
    },
    "SMKP.EXE": {
        "pages": 21,
        "straddlers": [0x11FFD, 0x1CFFE],
        "bss_cut": (0x32FF6, 2),
        "kinds": {"off32": 2297, "sel16": 0, "ptr16:32": 0, "rel32": 0},
    },
}

failures = 0


def claim(ok: bool, text: str, name: str, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name:<10} {text}{'  ' + detail if detail else ''}")


def hexes(values) -> str:
    return " ".join(f"{v:#x}" for v in values)


def check_pages(raw: RawLE, name: str, exp: dict) -> None:
    claim(raw.num_pages == exp["pages"], f"page count {raw.num_pages}", name)
    claim(len(raw.pages) == raw.num_pages, "page map has one entry per page", name)
    claim(all(p.flags == 0 for p in raw.pages), "every page-map flag is 0 (physical)", name)
    identity = all(p.number_be24 == p.logical for p in raw.pages)
    claim(identity, "identity map (24-bit big-endian page number == logical)", name)
    other = sum(p.number_spec == p.logical for p in raw.pages)
    print(f"INFO  {name:<10} u16-LE<<8 reading matches logical on {other}/{raw.num_pages} pages")
    claim(raw.pages_end <= len(raw.data), "pages end inside the file", name,
          f"pages_end={raw.pages_end:#x} size={len(raw.data):#x}")
    covered = sum(o.page_count for o in raw.objects)
    claim(covered == raw.num_pages, "objects cover every page exactly once", name)


def straddles(raw: RawLE, va: int, size: int) -> bool:
    return (va // raw.page_size) != ((va + size - 1) // raw.page_size)


def check_fixups(raw: RawLE, name: str, exp: dict) -> list[RawFixup]:
    try:
        recs = raw.fixup_records()
    except ValueError as exc:
        claim(False, f"every record is a plain internal fixup ({exc})", name)
        return []
    claim(True, f"every record is a plain internal fixup ({len(recs)} entries, raw)", name)
    by_va: dict[int, list[RawFixup]] = defaultdict(list)
    for r in recs:
        by_va[r.va].append(r)
    same_page_dups = sum(
        len(rs) != len({r.logical for r in rs}) for rs in by_va.values()
    )
    claim(same_page_dups == 0, "no field listed twice on the same page", name)

    twice = {va for va, rs in by_va.items() if len(rs) > 1}
    crossing = {va for va, rs in by_va.items() if straddles(raw, va, rs[0].size)}
    claim(all(len(by_va[va]) == 2 for va in twice), "no field listed more than twice", name)
    claim(twice == crossing, "fields listed twice == fields crossing a page boundary", name,
          f"twice={len(twice)} crossing={len(crossing)}")
    for va in sorted(crossing):
        rs = by_va[va]
        pages = sorted(r.logical for r in rs)
        first = va // raw.page_size
        want = sorted({raw.object_of_page(r.logical).index for r in rs})
        same = len({(r.kind, r.target_obj, r.target_off) for r in rs}) == 1
        adjacent = len(pages) == 2 and pages[1] == pages[0] + 1
        claim(same and adjacent and len(want) == 1,
              f"straddler {va:#x} on pages {pages} with one kind/target", name,
              f"vapage={first:#x}")
    kinds = {KIND_NAME.get(by_va[va][0].kind, "?") for va in crossing}
    objs = {raw.object_of_page(by_va[va][0].logical).index for va in crossing}
    claim(sorted(crossing) == exp["straddlers"],
          f"straddler VAs == expected ({len(crossing)})", name, hexes(sorted(crossing)))
    claim(kinds <= {"off32"}, f"straddlers are off32 only ({sorted(kinds)})", name)
    claim(objs <= {1}, f"straddlers are in object 1 only ({sorted(objs)})", name)
    return [rs[0] for _, rs in sorted(by_va.items())]


def check_bss_cut(raw: RawLE, name: str, exp: dict, fields: list[RawFixup]) -> None:
    cut = []
    over_vsize = 0
    for f in fields:
        obj = next(o for o in raw.objects if o.base <= f.va < o.base + o.vsize)
        end = raw.backed_end(obj)
        if f.va + f.size > obj.base + obj.vsize:
            over_vsize += 1
        if f.va < end < f.va + f.size:
            cut.append((f, obj, end))
    claim(over_vsize == 0, "no field crosses its object's vsize end", name)
    claim(len(cut) == 1, f"exactly one field cut by the end of page data ({len(cut)})", name)
    if len(cut) != 1:
        return
    f, obj, end = cut[0]
    short = raw.pages[f.logical - 1].number_be24 == raw.num_pages
    claim(KIND_NAME.get(f.kind) == "off32", "the cut field is off32", name)
    claim(short, "the cut field sits in the short last page", name,
          f"logical={f.logical} last_page_size={raw.last_page_size:#x}")
    claim((f.va, end - f.va) == exp["bss_cut"],
          "cut field VA and backed bytes == expected", name,
          f"va={f.va:#x} backed={end - f.va} bss={f.va + f.size - end} obj={obj.index} "
          f"target_obj={f.target_obj}")


def check_kinds(name: str, exp: dict, fields: list[RawFixup]) -> None:
    counts = Counter(KIND_NAME.get(f.kind, f"type{f.kind:#x}") for f in fields)
    got = {k: counts.get(k, 0) for k in exp["kinds"]}
    extra = sorted(set(counts) - set(exp["kinds"]))
    claim(got == exp["kinds"] and not extra, "de-duplicated kind counts == expected", name,
          f"{dict(counts)}")


def check_le_py(raw: RawLE, name: str, fields: list[RawFixup], path: Path) -> None:
    le = LE(path)
    claim((le.stub_offset, le.le_offset) == (raw.stub, raw.le),
          "le.py stub/LE offsets == raw", name, f"stub={raw.stub:#x} le={raw.le:#x}")
    raw_pages = [
        (p.logical, p.number_be24, p.flags, raw.page_file_offset(p.number_be24),
         raw.page_size_of(p.number_be24))
        for p in raw.pages
    ]
    py_pages = [(p.logical, p.number, p.flags, p.file_offset, p.size) for p in le.pages]
    claim(raw_pages == py_pages, "le.pages == raw page map field for field", name)
    raw_set = {
        (f.va, f.kind, raw.objects[f.target_obj - 1].base + f.target_off, f.target_obj,
         f.target_off, f.size)
        for f in fields
    }
    py_set = {
        (x.src_va, x.kind, x.target_va, x.target_obj, x.target_off, x.size) for x in le.fixups()
    }
    claim(raw_set == py_set, "le.fixups() == de-duplicated raw fields", name,
          f"raw={len(raw_set)} le.py={len(py_set)} only_raw={len(raw_set - py_set)} "
          f"only_le={len(py_set - raw_set)}")


def main() -> int:
    orig = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "orig"
    for name, exp in EXPECTED.items():
        path = orig / name
        if not path.is_file():
            claim(False, "file present", name, str(path))
            continue
        raw = RawLE(path.read_bytes())
        claim(raw.locate_method == "mz-chain", "stub found by the MZ -> BW header chain", name,
              f"stub={raw.stub:#x} le={raw.le:#x}")
        claim(locate_by_forward_scan(raw.data) == (raw.stub, raw.le),
              "forward MZ scan agrees with the header chain", name)
        check_pages(raw, name, exp)
        fields = check_fixups(raw, name, exp)
        check_bss_cut(raw, name, exp, fields)
        check_kinds(name, exp, fields)
        check_le_py(raw, name, fields, path)
    print(f"{'ALL PASS' if failures == 0 else f'{failures} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

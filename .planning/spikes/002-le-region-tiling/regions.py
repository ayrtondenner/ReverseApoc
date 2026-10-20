"""Spike 002: cut each EXE into byte regions from its own LE header and reassemble it.

Run: uv run python .planning/spikes/002-le-region-tiling/regions.py [ORIG_DIR]
Reads orig/ only, writes nothing, prints offsets, lengths, counts, booleans and SHA-1s only.
Exit 1 when any claim fails.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

from reverseapoc.le import LE
from reverseapoc.targets import load_manifest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def _load_rawle():
    path = HERE.parent / "001-le-pages-and-fixups" / "rawle.py"
    spec = importlib.util.spec_from_file_location("rawle", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rawle"] = module  # dataclasses look the module up while building classes
    spec.loader.exec_module(module)
    return module


rawle = _load_rawle()

# Provisional facts from 03-RESEARCH.md "Region boundaries" and "Objects, page backing and BSS".
EXPECTED = {
    "UFO2P.EXE": {
        "starts": [0, 0x352A4, 0x37F34, 0x37FF8, 0x384EE, 0x7233A, 0x724A4, 0x1A0723],
        "padding": 362,
        "obj1_tail": 0x523,
        "trailer": 27,
    },
    "TACP.EXE": {
        "starts": [0, 0x352A4, 0x37F34, 0x37FF8, 0x38A99, 0x6A711, 0x6A8A4, 0x303DDF],
        "padding": 403,
        "obj1_tail": 0xAB1,
        "trailer": 27,
    },
    "SMKP.EXE": {
        "starts": [0, 0x26654, 0x292E4, 0x293A8, 0x29435, 0x2D375, 0x2D454],
        "padding": 223,
        "obj1_tail": 0xC80,
        "trailer": 0,
    },
}
NAMES = ["extender", "MZ stub", "LE header", "loader tables", "fixup section", "padding",
         "pages", "trailer"]

failures = 0


def claim(ok: bool, text: str, name: str, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name:<10} {text}{'  ' + detail if detail else ''}")


def regions(raw) -> list[tuple[str, int, int]]:
    """Half-open regions from the raw header fields; zero-length regions are dropped."""
    fixup_end = raw.fixup_page_table + raw.fixup_section_size
    bounds = [0, raw.stub, raw.le, raw.object_table, raw.fixup_page_table, fixup_end,
              raw.data_pages, raw.pages_end, len(raw.data)]
    spans = zip(NAMES, bounds, bounds[1:], strict=False)
    return [(n, a, b) for n, a, b in spans if b != a]


def tiles(regs: list[tuple[str, int, int]], size: int) -> bool:
    ends = [0] + [b for _, _, b in regs]
    starts = [a for _, a, _ in regs] + [size]
    return ends == starts and all(a < b for _, a, b in regs)


def object_image(raw, obj, vsize_only: bool = False) -> bytearray:
    """page_count * page_size bytes filled from each page's full size through the page map.

    vsize_only is the D-16 mutant that stops at vsize, as a flat loader does."""
    image = bytearray(obj.page_count * raw.page_size)
    for k in range(obj.page_count):
        page = raw.pages[obj.page_index - 1 + k]
        src = raw.page_file_offset(page.number_be24)
        n = raw.page_size_of(page.number_be24)
        image[k * raw.page_size : k * raw.page_size + n] = raw.data[src : src + n]
    if vsize_only:
        image[obj.vsize :] = bytes(max(0, len(image) - obj.vsize))
    return image


def reassemble(raw, regs, dest=None, vsize_only: bool = False, reverse: bool = False):
    """Fresh buffer: non-page regions sliced from the original, pages re-paged from images.

    dest(page) gives the physical page number a page's bytes are written to (default: the map's
    own number); the mutants pass a wrong one. reverse writes everything in reverse order."""
    dest = dest or (lambda page: page.number_be24)
    order = reversed if reverse else iter
    out = bytearray(len(raw.data))
    for name, a, b in order(regs):
        if name != "pages":
            out[a:b] = raw.data[a:b]
    for obj in order(raw.objects):
        image = object_image(raw, obj, vsize_only)
        for k in order(range(obj.page_count)):
            page = raw.pages[obj.page_index - 1 + k]
            dst = raw.page_file_offset(dest(page))
            n = raw.page_size_of(page.number_be24)
            out[dst : dst + n] = image[k * raw.page_size : k * raw.page_size + n]
    return out


def check_file(name: str, path: Path, sha1: str, exp: dict) -> None:
    raw = rawle.RawLE(path.read_bytes())
    d = raw.data
    regs = regions(raw)
    for n, a, b in regs:
        print(f"INFO  {name:<10} {n:<14} [{a:#x}, {b:#x})  {b - a} bytes")
    claim(tiles(regs, len(d)), "regions tile [0, size) with no gap or overlap", name,
          f"sum={sum(b - a for _, a, b in regs)} size={len(d)}")
    claim([a for _, a, _ in regs] == exp["starts"], "region starts == 03-RESEARCH table", name)
    loader_end = raw.object_table + raw.loader_section_size
    fixup_end = raw.fixup_page_table + raw.fixup_section_size
    claim(loader_end == fixup_end, "declared loader section ends where the fixup section ends",
          name, f"{loader_end:#x} vs {fixup_end:#x}")
    claim(raw.fixup_page_table + 4 * (raw.num_pages + 1) == raw.fixup_record_table,
          "fixup page table has num_pages + 1 entries", name)
    claim(raw.header(rawle.LE_ITER_DATA_MAP) == 0, "no iterated data map", name)
    zero_fields = {
        "non-resident name table": rawle.LE_NONRES_NAME_TABLE,
        "non-resident name length": rawle.LE_NONRES_NAME_LENGTH,
        "debug info": rawle.LE_DEBUG_INFO,
        "debug length": rawle.LE_DEBUG_LENGTH,
    }
    nonzero = [label for label, f in zero_fields.items() if raw.header(f) != 0]
    claim(not nonzero, "non-resident name and debug fields are zero", name, str(nonzero))

    pad = next(((a, b) for n, a, b in regs if n == "padding"), (0, 0))
    claim(pad[1] - pad[0] == exp["padding"], f"padding length {pad[1] - pad[0]}", name)
    claim(not any(d[pad[0] : pad[1]]), "padding is all zero", name)

    obj1 = raw.objects[0]
    tail = raw.backed_end(obj1) - obj1.base - obj1.vsize
    tail_start = raw.page_file_offset(raw.pages[obj1.page_index + obj1.page_count - 2].number_be24)
    tail_start += raw.page_size - tail
    claim(tail == exp["obj1_tail"], f"obj1 page bytes past vsize {tail:#x}", name)
    claim(not any(d[tail_start : tail_start + tail]), "obj1 page tail past vsize is all zero",
          name)

    trailer = len(d) - raw.pages_end
    claim(trailer == exp["trailer"], f"bytes after the last page {trailer}", name,
          f"at {raw.pages_end:#x}")

    le = LE(path)
    claim((le.data_pages_offset, le.last_page_size, le.num_pages)
          == (raw.data_pages, raw.last_page_size, raw.num_pages),
          "le.py data-pages offset, last page size and page count == raw", name)
    le_pages_end = max(p.file_offset + p.size for p in le.pages)
    claim(le_pages_end == raw.pages_end, "le.py page geometry ends where raw pages end", name)

    out = reassemble(raw, regs)
    got = hashlib.sha1(out).hexdigest()
    claim(got == sha1, "reassembled SHA-1 == load_manifest() sha1", name, got)
    mid = raw.page_file_offset(raw.num_pages // 2) + raw.page_size // 2
    out[mid] ^= 0xFF
    claim(hashlib.sha1(out).hexdigest() != sha1, "one flipped page byte changes the SHA-1",
          name, f"flipped at {mid:#x}")
    ordered = reassemble(raw, regs, reverse=True)
    claim(hashlib.sha1(ordered).hexdigest() == sha1,
          "reassembly in reverse region/object/page order gives the same SHA-1", name)
    check_mutants(raw, regs, name, sha1)


def _caught(out: bytearray, sha1: str) -> bool:
    return hashlib.sha1(out).hexdigest() != sha1


def check_mutants(raw, regs, name: str, sha1: str) -> None:
    """D-16 mutants: which wrong reassemblies the real file's SHA-1 can and cannot catch."""
    swap = {1: 2, 2: 1}
    out = reassemble(raw, regs, dest=lambda p: swap.get(p.number_be24, p.number_be24))
    claim(_caught(out, sha1), "mutant: pages 1/2 written to each other's slot is caught", name)

    no_trailer = reassemble(raw, [r for r in regs if r[0] != "trailer"])
    has_trailer = any(r[0] == "trailer" for r in regs)
    claim(_caught(no_trailer, sha1) == has_trailer,
          "mutant: dropping the trailer region is caught iff one exists", name,
          f"caught={_caught(no_trailer, sha1)}")

    vsize = _caught(reassemble(raw, regs, vsize_only=True), sha1)
    logical = _caught(reassemble(raw, regs, dest=lambda p: p.logical), sha1)
    print(f"INFO  {name:<10} mutant: vsize-sized images caught={vsize} "
          f"(page tail past vsize is all zero)")
    print(f"INFO  {name:<10} mutant: logical-number page offsets caught={logical} "
          f"(identity page map)")


def main() -> int:
    orig = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "orig"
    for target in load_manifest():
        exp = EXPECTED.get(target.name)
        path = orig / target.name
        if exp is None or not path.is_file():
            claim(False, "target known and present", target.name, str(path))
            continue
        check_file(target.name, path, target.sha1, exp)
    print(f"{'ALL PASS' if failures == 0 else f'{failures} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

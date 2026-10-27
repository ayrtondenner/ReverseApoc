"""Spike 007 q5: OpenApoc's CD-build data-table offsets re-located in the installed build by VA
identity (D-03 / Phase 6 D-42; research Q3).

OpenApoc's extractor headers give `*_OFFSET_START` / `*_OFFSET_END` as file offsets into the CD
v1.00 EXEs. Research found that the CD and installed data objects share base and end, so a CD
file offset maps through the CD LE page map to a linear address, and the installed bytes at that
address are the same table. The CD EXEs are read from the Steam cd.iso in memory
(reverseapoc.iso9660, spike 003); their size and SHA-1 are checked against `[[cd_builds]]` in
config/targets.toml (tomllib).

Claims, per EXE:
- cd-build: the disc file matches `[[cd_builds]]` (size, SHA-1);
- data-object-identity: the CD and installed data objects have the same base and size, and the
  count of identical 4 KB pages and of differing bytes over the object equal research Q3 (UFO2P)
  and this spike's first run (TACP);
Then, over both EXEs:
- tables-va-identity (only with headers): every header span whose [start, end) maps into a CD
  EXE's data object has installed bytes equal to the CD bytes at the same linear address, in
  every EXE it maps into (the headers do not say which EXE a span belongs to, so a span is tried
  in both; a span that maps into both is counted as ambiguous). The spans mapped equal research
  Q3's 35 + 12 tables. Per EXE the mapped, identical and with-code-refs counts (game/thunk rows
  holding a fixup into the span) are reported. The headers are read as text from the gitignored
  build/openapoc-extractors/*.h (regex, never imported, never committed); without them q5 prints
  `SKIP q5 headers absent`.

Run from the main checkout:
    uv run python .planning/spikes/007-locate-997-training/q5_tables.py [--plant] [--headers DIR]

--plant flips one byte of the installed image in memory (inside the first header table, or with
no headers inside the first identical data page); the run must FAIL. Prints offsets, addresses,
counts and SHA-1s only: never table bytes, header text or OpenApoc names. Reads orig/, the disc
image and the headers read-only, writes nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from q1_timebase import EXES, REPO, Image, Report, hx, raw_flat, rawle
from q3_training import OBJ_EXECUTABLE

from reverseapoc.iso9660 import ISO9660

STEAM = Path(r"C:\Program Files (x86)\Steam\steamapps\common\XCom Apocalypse")
HEADERS = REPO / "build" / "openapoc-extractors"
PAGE = 0x1000
DEFINE = re.compile(r"^\s*#\s*define\s+(\w+)_OFFSET_(START|END)\s+(0[xX][0-9A-Fa-f]+|\d+)", re.M)

# Copied from 07-R1-locate.md Q3 ("Measured", "Xref yield"); the TACP page counts were measured
# by this script's first run ("this spike") and are pinned here.
EXPECTED = {
    "spans_mapped": 47,  # 35 UFO2P + 12 TACP tables (2 TACP sprite offsets do not map)
    "UFO2P.EXE": {"data": (0x000D0000, 0x00251E20), "pages_identical": 380, "pages": 386,
                  "bytes_differ": 258, "tables": 35, "with_refs": 23},
    "TACP.EXE": {"data": (0x000E0000, 0x0033F0B0), "pages_identical": 605, "pages": 608,
                 "bytes_differ": 190, "tables": 12, "with_refs": 10},  # pages: this spike
}  # fmt: skip


@dataclass(frozen=True)
class Span:
    start: int  # CD file offset
    end: int


def cd_builds() -> dict[str, dict]:
    with (REPO / "config" / "targets.toml").open("rb") as fh:
        return {b["name"]: b for b in tomllib.load(fh)["cd_builds"]}


def disc_files(iso_path: Path, builds: dict[str, dict]) -> dict[str, bytes]:
    out = {}
    with ISO9660.open(iso_path) as iso:
        for name, build in builds.items():
            buf = io.BytesIO()
            iso.copy_to(iso.find(build["path"]), buf)
            out[name] = buf.getvalue()
    return out


def data_object(raw):
    return next(o for o in raw.objects if not o.flags & OBJ_EXECUTABLE)


def file_to_va(raw, offset: int) -> int | None:
    """The linear address a CD file offset lands on through the LE page map, or None."""
    for logical, page in enumerate(raw.pages, start=1):
        at = raw.page_file_offset(page.number_be24)
        if at <= offset < at + raw.page_size_of(page.number_be24):
            return raw.page_va(logical) + offset - at
    return None


def header_spans(folder: Path) -> list[Span] | None:
    files = sorted(folder.glob("*.h")) if folder.is_dir() else []
    if not files:
        return None
    found: dict[str, dict[str, int]] = {}
    for path in files:
        for name, kind, value in DEFINE.findall(path.read_text(encoding="utf-8", errors="replace")):
            found.setdefault(name, {})[kind] = int(value, 0)
    return [Span(v["START"], v["END"]) for _, v in sorted(found.items())
            if "START" in v and "END" in v and v["END"] > v["START"]]  # fmt: skip


def page_identity(cd_flat: bytes, flat: bytes, base: int, size: int) -> tuple[int, int, int]:
    pages = (size + PAGE - 1) // PAGE
    same = 0
    differ = 0
    for k in range(pages):
        lo, hi = base + k * PAGE, min(base + (k + 1) * PAGE, base + size)
        a, b = cd_flat[lo:hi], flat[lo:hi]
        same += a == b
        if a != b:
            differ += sum(x != y for x, y in zip(a, b, strict=True))
    return same, pages, differ


def claim_build(report: Report, name: str, data: bytes, build: dict) -> bool:
    sha = hashlib.sha1(data).hexdigest()
    ok = len(data) == build["size"] and sha == build["sha1"]
    report.claim(name, ok, "cd-build", f"{build['path']} size {len(data)} sha1 {sha} "
                 f"expected size {build['size']} sha1 {build['sha1']}")  # fmt: skip
    return ok


def claim_identity(report: Report, img: Image, cd, cd_flat: bytes, flat: bytes,
                   exp: dict) -> None:  # fmt: skip
    mine, theirs = data_object(img.raw), data_object(cd)
    same_obj = (mine.base, mine.vsize) == (theirs.base, theirs.vsize)
    base, size = mine.base, mine.vsize
    same, pages, differ = page_identity(cd_flat, flat, base, size)
    ok = same_obj and (base, base + size) == exp["data"]
    for key, got in (("pages_identical", same), ("pages", pages), ("bytes_differ", differ)):
        if exp[key] is not None:
            ok = ok and got == exp[key]
    report.claim(img.name, ok, "data-object-identity",
                 f"installed [{hx(base)}..{hx(base + size)}) CD [{hx(theirs.base)}.."
                 f"{hx(theirs.base + theirs.vsize)}) same {same_obj}; identical pages {same} of "
                 f"{pages}; differing bytes {differ}; expected {exp['pages_identical']} of "
                 f"{exp['pages']}, {exp['bytes_differ']}")  # fmt: skip


def map_span(cd, span: Span) -> int | None:
    """The linear address of a span that maps contiguously into the CD EXE's data object."""
    obj = data_object(cd)
    lo, last = file_to_va(cd, span.start), file_to_va(cd, span.end - 1)
    if lo is None or last is None or last - lo != span.end - 1 - span.start:
        return None
    return lo if obj.base <= lo and last < obj.base + obj.vsize else None


def has_code_refs(img: Image, va: int, n: int) -> bool:
    return any(va <= f.target < va + n and (row := img.row_at(f.va)) is not None
               and row.kind in ("game", "thunk") for f in img.fields.values())  # fmt: skip


def claim_tables(report: Report, loaded: dict, spans: list[Span]) -> None:
    mapped = {name: 0 for name in loaded}
    identical = {name: 0 for name in loaded}
    with_refs = {name: 0 for name in loaded}
    any_mapped, ambiguous, differ = 0, 0, []
    for span in spans:
        hits = 0
        for name, (img, cd, cd_flat, flat) in loaded.items():
            va = map_span(cd, span)
            if va is None:
                continue
            n = span.end - span.start
            hits += 1
            mapped[name] += 1
            if cd_flat[va : va + n] == flat[va : va + n]:
                identical[name] += 1
                with_refs[name] += has_code_refs(img, va, n)
            else:
                differ.append(f"{name.split('.')[0]}:{hx(va)}")
        any_mapped += bool(hits)
        ambiguous += hits > 1
    ok = any_mapped == EXPECTED["spans_mapped"] and not differ
    counts = "; ".join(f"{name.split('.')[0]} mapped {mapped[name]} identical {identical[name]} "
                       f"with code refs {with_refs[name]} (research {EXPECTED[name]['tables']} "
                       f"tables, {EXPECTED[name]['with_refs']} with refs)" for name in loaded)
    report.claim("q5", ok, "tables-va-identity",
                 f"header spans {len(spans)}; mapped into a data object {any_mapped} (expected "
                 f"{EXPECTED['spans_mapped']}), into both EXEs {ambiguous}; {counts}; "
                 f"differing at [{' '.join(differ)}]")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", action="store_true", help="flip one installed byte in memory")
    parser.add_argument("--headers", type=Path, default=HEADERS, help="folder of extractor .h")
    parser.add_argument("--game", type=Path, default=STEAM, help="folder holding cd.iso")
    args = parser.parse_args(argv)
    spans = header_spans(args.headers)
    if spans is None:
        print(f"SKIP q5 headers absent ({args.headers})")
    builds = cd_builds()
    disc = disc_files(args.game / "cd.iso", builds)
    report = Report()
    loaded = {}
    for name in EXES:
        img = Image(name)
        exp = EXPECTED[name]
        if not claim_build(report, name, disc[name], builds[name]):
            continue
        cd = rawle.RawLE(disc[name])
        cd_flat = bytes(raw_flat(cd))
        flat = bytearray(img.flat)
        if args.plant and name == EXES[0]:
            target = None
            for span in spans or ():
                if (target := map_span(cd, span)) is not None:
                    break
            if target is None:
                obj = data_object(img.raw)
                target = next(obj.base + k * PAGE for k in range(obj.vsize // PAGE)
                              if cd_flat[obj.base + k * PAGE : obj.base + (k + 1) * PAGE]
                              == flat[obj.base + k * PAGE : obj.base + (k + 1) * PAGE])  # fmt: skip
            flat[target] ^= 0xFF
            print(f"PLANT {name} installed byte at {hx(target)} flipped in memory")
        claim_identity(report, img, cd, cd_flat, bytes(flat), exp)
        loaded[name] = (img, cd, cd_flat, bytes(flat))
    if spans is not None:
        claim_tables(report, loaded, spans)
    return report.finish()


if __name__ == "__main__":
    sys.exit(main())

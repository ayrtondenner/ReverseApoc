"""Spike 003 follow-up: structure of the 27-byte trailer across the four builds that carry it.

Run: uv run python .planning/spikes/003-trailer/followup.py [ORIG_DIR] [GAME_DIR]
Prints SHA-1 equalities, trailer positions, booleans and counts only; never trailer bytes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import sys
from pathlib import Path

from reverseapoc.iso9660 import ISO9660
from reverseapoc.targets import load_manifest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
STEAM = Path(r"C:\Program Files (x86)\Steam\steamapps\common\XCom Apocalypse")
CD_FILES = ["XCOM3/UFOEXE/UFO2P.EXE", "XCOM3/UFOEXE/UFO2P4.EXE", "XCOM3/TACEXE/TACP.EXE",
            "XCOM3/TACEXE/TACP4.EXE"]
PAIRS = (0, 4, 8)  # trailer positions of the u16 value/complement pairs


def _load_rawle():
    path = HERE.parent / "001-le-pages-and-fixups" / "rawle.py"
    spec = importlib.util.spec_from_file_location("rawle", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rawle"] = module
    spec.loader.exec_module(module)
    return module


rawle = _load_rawle()


def crc16(data: bytes, poly: int, init: int, reflect: bool) -> int:
    """Bitwise CRC-16 (ARC: 0xA001 reflected, init 0; CCITT-FALSE: 0x1021, init 0xFFFF)."""
    crc = init
    for b in data:
        if reflect:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ poly if crc & 1 else crc >> 1
        else:
            crc ^= b << 8
            for _ in range(8):
                crc = ((crc << 1) ^ poly) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def u16_candidates(raw, d: bytes) -> dict[str, int]:
    end = raw.pages_end
    obj_ranges = {}
    for obj in raw.objects:
        first = raw.page_file_offset(raw.pages[obj.page_index - 1].number_be24)
        last = raw.pages[obj.page_index + obj.page_count - 2].number_be24
        stop = raw.page_file_offset(last) + raw.page_size_of(last)
        obj_ranges[f"obj{obj.index} pages"] = d[first:stop]
    ranges = {"file-before-trailer": d[:end], "LE image": d[raw.stub : end],
              "pages": d[raw.data_pages : end], **obj_ranges}
    out = {}
    for rname, blob in ranges.items():
        words = [int.from_bytes(blob[i : i + 2], "little") for i in range(0, len(blob) - 1, 2)]
        out[f"wordsum({rname})"] = sum(words) & 0xFFFF
        out[f"bytesum({rname})"] = sum(blob) & 0xFFFF
        out[f"xorword({rname})"] = _xor_words(words)
        out[f"crc16-arc({rname})"] = crc16(blob, 0xA001, 0, True)
        out[f"crc16-ccitt({rname})"] = crc16(blob, 0x1021, 0xFFFF, False)
    out["file size"] = len(d)
    out["file size >> 4"] = len(d) >> 4
    out["pages_end >> 4"] = end >> 4
    return out


def _xor_words(words: list[int]) -> int:
    x = 0
    for w in words:
        x ^= w
    return x


def main() -> int:
    orig = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "orig"
    game = Path(sys.argv[2]) if len(sys.argv) > 2 else STEAM
    manifest = {t.name: t.sha1 for t in load_manifest()}
    files = {}
    with ISO9660.open(game / "cd.iso") as iso:
        for path in CD_FILES:
            buf = io.BytesIO()
            iso.copy_to(iso.find(path), buf)
            files[f"cd:{path.rsplit('/', 1)[1]}"] = buf.getvalue()
    for name in ("UFO2P.EXE", "TACP.EXE"):
        files[f"orig:{name}"] = (orig / name).read_bytes()

    print("== whole-file identity")
    for label, d in files.items():
        sha = hashlib.sha1(d).hexdigest()
        same = [n for n, s in manifest.items() if s == sha]
        print(f"{label:<16} sha1 {sha} == manifest target {same or '-'}")

    trailers = {}
    raws = {}
    for label, d in files.items():
        raw = rawle.RawLE(d)
        raws[label] = raw
        trailers[label] = d[raw.pages_end :]

    print("\n== trailer positions shared by all four distinct builds (CD v1.00 + '4' builds)")
    distinct = [trailers[k] for k in ("cd:UFO2P.EXE", "cd:UFO2P4.EXE", "cd:TACP.EXE",
                                      "cd:TACP4.EXE")]
    shared = [p for p in range(27) if len({t[p] for t in distinct}) == 1]
    print(f"positions equal in all four: {shared}")
    for p in PAIRS:
        vals = [int.from_bytes(t[p : p + 2], "little") for t in distinct]
        print(f"pair@{p}: complement holds in all four={all(_pair_ok(t, p) for t in distinct)} "
              f"value equal across all four={len(set(vals)) == 1} "
              f"UFO2P==UFO2P4={vals[0] == vals[1]} TACP==TACP4={vals[2] == vals[3]}")
    tail = [p for p in range(12, 27) if len({t[p] for t in distinct}) == 1]
    print(f"positions 12..26 equal in all four: {tail}")

    print("\n== 16-bit candidates for the pair values @4 and @8 (and @0)")
    for label in ("cd:UFO2P.EXE", "cd:UFO2P4.EXE", "cd:TACP.EXE", "cd:TACP4.EXE"):
        t = trailers[label]
        cands = u16_candidates(raws[label], files[label])
        hits = [f"{n}@{p}" for p in PAIRS for n, c in cands.items()
                if int.from_bytes(t[p : p + 2], "little") in (c & 0xFFFF, (~c) & 0xFFFF)]
        print(f"{label:<16} {len(cands)} candidates, hits: {hits}")

    print("\n== which files on the disc name the '4' builds? (paths and counts only)")
    with ISO9660.open(game / "cd.iso") as iso:
        for entry in iso.walk():
            if entry.is_dir or entry.size > 4 << 20:
                continue
            buf = io.BytesIO()
            iso.copy_to(entry, buf)
            blob = buf.getvalue().upper()
            counts = {k: blob.count(k) for k in (b"UFO2P4", b"TACP4")}
            if any(counts.values()):
                print(f"cd:{entry.path:<30} UFO2P4={counts[b'UFO2P4']} TACP4={counts[b'TACP4']}")

    print("\n== does the code mention the trailer? (counts of 32-bit immediates in pages)")
    for label in ("orig:UFO2P.EXE", "orig:TACP.EXE"):
        raw, d = raws[label], files[label]
        pages = d[raw.data_pages : raw.pages_end]
        for name, value in (("-27", -27 & 0xFFFFFFFF), ("27", 27), ("-12", -12 & 0xFFFFFFFF),
                            ("0xFF9B0064", 0xFF9B0064)):
            print(f"{label:<16} u32le {name:>10}: {pages.count(value.to_bytes(4, 'little'))}")
    return 0


def _pair_ok(t: bytes, p: int) -> bool:
    a = int.from_bytes(t[p : p + 2], "little")
    b = int.from_bytes(t[p + 2 : p + 4], "little")
    return b == (~a) & 0xFFFF


if __name__ == "__main__":
    sys.exit(main())

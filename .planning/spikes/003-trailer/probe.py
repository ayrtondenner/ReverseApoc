"""Spike 003: what are the bytes after the last LE page (D-10)? Time-boxed hypothesis probe.

Run: uv run python .planning/spikes/003-trailer/probe.py [ORIG_DIR] [GAME_DIR]
GAME_DIR (default: the Steam install) holds cd.iso and XCOMA/. Everything is read in memory;
nothing is written. Printed: offsets, lengths, counts, booleans, trailer positions, the first
4 trailer bytes and SHA-1s. Trailer bytes past the first 4 are never printed; hypotheses are
compared inside the script and reported as matches by name and trailer position.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import sys
import tomllib
import zlib
from datetime import date
from pathlib import Path

from reverseapoc.iso9660 import ISO9660
from reverseapoc.targets import load_manifest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
STEAM = Path(r"C:\Program Files (x86)\Steam\steamapps\common\XCom Apocalypse")


def _load_rawle():
    path = HERE.parent / "001-le-pages-and-fixups" / "rawle.py"
    spec = importlib.util.spec_from_file_location("rawle", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rawle"] = module  # dataclasses look the module up while building classes
    spec.loader.exec_module(module)
    return module


rawle = _load_rawle()


def facts(label: str, d: bytes) -> tuple[object, bytes] | None:
    """Print the post-page facts of one LE file; return (RawLE, trailer) or None."""
    try:
        raw = rawle.RawLE(d)
    except (ValueError, IndexError) as exc:
        print(f"{label:<34} not a bound LE ({type(exc).__name__})")
        return None
    t = d[raw.pages_end :]
    head = " ".join(f"{b:02x}" for b in t[:4])
    sha = hashlib.sha1(t).hexdigest()
    print(f"{label:<34} size={len(d):#x} pages_end={raw.pages_end:#x} after={len(t)}"
          f"{f'  starts {head}  sha1 {sha}' if t else ''}")
    return raw, t


def sums(b: bytes) -> dict[str, int]:
    words = [int.from_bytes(b[i : i + 2], "little") for i in range(0, len(b) - 1, 2)]
    sum16 = sum(words) & 0xFFFF
    return {
        "crc32": zlib.crc32(b),
        "adler32": zlib.adler32(b),
        "sum8": sum(b) & 0xFF,
        "sum16": sum16,
        "sum32": sum(b) & 0xFFFFFFFF,
        "wordsum16": sum(words) & 0xFFFF,
        "mz_checksum": (~sum16) & 0xFFFF,
        "wordsum32": sum(words) & 0xFFFFFFFF,
    }


def candidates(raw, d: bytes) -> dict[str, int]:
    end = raw.pages_end
    out = {
        "file size": len(d),
        "pages_end": end,
        "data_pages": raw.data_pages,
        "stub": raw.stub,
        "le": raw.le,
        "num_pages": raw.num_pages,
        "last_page_size": raw.last_page_size,
        "fixup_section_size": raw.fixup_section_size,
        "loader_section_size": raw.loader_section_size,
        "pages bytes": end - raw.data_pages,
        "LE image bytes": end - raw.stub,
    }
    ranges = {
        "file-before-trailer": d[:end],
        "pages": d[raw.data_pages : end],
        "LE image": d[raw.stub : end],
        "extender": d[: raw.stub],
    }
    for rname, blob in ranges.items():
        for sname, value in sums(blob).items():
            out[f"{sname}({rname})"] = value
    return out


def field_matches(t: bytes, cands: dict[str, int]) -> list[str]:
    """Every (candidate, width, endianness, position) whose value appears in the trailer."""
    hits = []
    for width in (2, 4):
        mask = (1 << (8 * width)) - 1
        for pos in range(len(t) - width + 1):
            for order in ("little", "big"):
                v = int.from_bytes(t[pos : pos + width], order)
                for name, c in cands.items():
                    if v == c & mask and v not in (0, mask):
                        hits.append(f"{name}@{pos} u{8 * width}{order[0]}")
    return hits


def complement_pairs(t: bytes) -> list[int]:
    """Positions p where u16le(p + 2) is the one's complement of u16le(p)."""
    w = [int.from_bytes(t[p : p + 2], "little") for p in range(len(t) - 1)]
    return [p for p in range(len(t) - 3) if w[p + 2] == (~w[p]) & 0xFFFF]


def dos_dates(t: bytes) -> list[int]:
    """Positions holding a u16le DOS date in 1994..1999."""
    found = []
    for p in range(len(t) - 1):
        v = int.from_bytes(t[p : p + 2], "little")
        y, m, dd = 1980 + (v >> 9), (v >> 5) & 0xF, v & 0x1F
        try:
            date(y, m, dd)
        except ValueError:
            continue
        if 1994 <= y <= 1999:
            found.append(p)
    return found


def shape(t: bytes) -> str:
    printable = sum(32 <= b < 127 for b in t)
    return (f"len={len(t)} zero={t.count(0)} ff={t.count(0xFF)} distinct={len(set(t))} "
            f"printable={printable}")


def iso_les(iso_path: Path) -> dict[str, bytes]:
    """Every .EXE on the disc image, read into memory."""
    out = {}
    with ISO9660.open(iso_path) as iso:
        for entry in iso.walk():
            if entry.is_dir or not entry.path.upper().endswith(".EXE"):
                continue
            buf = io.BytesIO()
            iso.copy_to(entry, buf)
            out[entry.path] = buf.getvalue()
    return out


def main() -> int:
    orig = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "orig"
    game = Path(sys.argv[2]) if len(sys.argv) > 2 else STEAM

    print("== installed builds (orig/)")
    installed = {}
    for target in load_manifest():
        d = (orig / target.name).read_bytes()
        got = facts(target.name, d)
        if got:
            installed[target.name] = (d, *got)

    print("\n== trailer comparison")
    tu, tt = installed["UFO2P.EXE"][2], installed["TACP.EXE"][2]
    same = sum(a == b for a, b in zip(tu, tt, strict=True))
    print(f"UFO2P vs TACP trailer: equal={tu == tt} equal_positions={same}/{len(tu)}")
    for name in ("UFO2P.EXE", "TACP.EXE"):
        t = installed[name][2]
        print(f"{name:<10} shape: {shape(t)}")
        print(f"{name:<10} u16 complement pairs at positions {complement_pairs(t)}")
        print(f"{name:<10} plausible DOS dates (1994-1999) at positions {dos_dates(t)}")

    print("\n== hypotheses: layout values and checksums inside the trailer")
    per_file = {}
    for name in ("UFO2P.EXE", "TACP.EXE"):
        d, raw, t = installed[name]
        hits = field_matches(t, candidates(raw, d))
        per_file[name] = {h.split("@")[0] + "@" + h.split("@")[1] for h in hits}
        print(f"{name:<10} {len(hits)} matches: {sorted(hits)}")
    both = per_file["UFO2P.EXE"] & per_file["TACP.EXE"]
    print(f"matches present in both files at the same position: {sorted(both)}")

    print("\n== CD v1.00 builds and other LE programs")
    cd_builds = {
        b["path"]: b["sha1"]
        for b in tomllib.loads((REPO / "config" / "targets.toml").read_text())["cd_builds"]
    }
    disc = iso_les(game / "cd.iso")
    for path, d in sorted(disc.items()):
        ok = ""
        if path.upper() in {p.upper() for p in cd_builds}:
            want = next(v for k, v in cd_builds.items() if k.upper() == path.upper())
            ok = f" [cd_builds sha1 match={hashlib.sha1(d).hexdigest() == want}]"
        got = facts(f"cd:{path}", d)
        if got and got[1]:
            t = got[1]
            print(f"{'':<34} equal to UFO2P trailer={t == tu} TACP trailer={t == tt}{ok} "
                  f"shape: {shape(t)} complement pairs {complement_pairs(t)}")
        elif ok:
            print(f"{'':<34}{ok}")
    for exe in sorted((game / "XCOMA").rglob("*.EXE")):
        facts(f"steam:{exe.relative_to(game)}", exe.read_bytes())
    return 0


if __name__ == "__main__":
    sys.exit(main())

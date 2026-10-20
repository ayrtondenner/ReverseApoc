"""Spike 001 side probe: follow the MZ/BW header chain of the bound DOS/4GW extender.

Run: uv run python .planning/spikes/001-le-pages-and-fixups/extender_chain.py [ORIG_DIR]
Prints header offsets, declared image sizes and whether a 2-byte format signature is MZ or BW.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rawle import (
    BW_NEXT_HEADER,
    BW_SIGNATURE,
    MZ_SIGNATURE,
    locate_by_forward_scan,
    mz_image_size,
    u32,
)

REPO = Path(__file__).resolve().parents[3]


def hops(d: bytes, stop: int) -> list[str]:
    out = []
    off = 0
    while 0 <= off < stop and len(out) < 16:
        sig = d[off : off + 2]
        if sig not in (MZ_SIGNATURE, BW_SIGNATURE):
            out.append(f"neither-MZ-nor-BW@{off:#x}")
            break
        size = mz_image_size(d, off)
        label = "MZ" if sig == MZ_SIGNATURE else "BW"
        extra = f" u32@0x1C={u32(d, off + BW_NEXT_HEADER):#x}" if label == "BW" else ""
        out.append(f"{label}@{off:#x}(image {size:#x}{extra})")
        if size <= 0:
            break
        # A BW header's u32 at 0x1C is followed as an absolute next-header offset; an MZ image
        # is followed by its declared size.
        off = u32(d, off + BW_NEXT_HEADER) if label == "BW" else off + size
    if off == stop:
        out.append(f"== stub@{stop:#x}")
    return out


def main() -> int:
    orig = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "orig"
    for name in ("UFO2P.EXE", "TACP.EXE", "SMKP.EXE"):
        d = (orig / name).read_bytes()
        found = locate_by_forward_scan(d)
        stub = found[0] if found else -1
        print(f"{name:<10} " + " -> ".join(hops(d, stub)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

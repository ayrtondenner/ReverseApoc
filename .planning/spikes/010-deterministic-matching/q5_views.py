# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 010 Q5: put converter matches into private views for the real gate.

    uv run python .planning/spikes/010-deterministic-matching/q5_views.py

For each MATCHES entry it copies the committed src/ tree to build/spike-010/view-N/src/ and
replaces the function's `INCLUDE_ASM(func_X);` with the converter's C (under the variant's
choice points), then prints the commands to run: `check --src` and `lint` in the container,
`readlint` on the host. Nothing tracked is written.
"""

from __future__ import annotations

import re
import shutil

from common import OUT, REPO_ROOT, exe_inputs
from lift import Lifter

from reverseapoc.units import scaffold_unit

# (exe, address, choice points): the two Q3 matches and the three Q4 variant matches
MATCHES = (
    ("ufo2p", 0x000520A0, {}),
    ("ufo2p", 0x000520E0, {}),
    ("tacp", 0x000A6000, {"force_ret": "void", "once": True}),
    ("tacp", 0x000A6080, {"force_ret": "void", "once": True}),
    ("ufo2p", 0x0002F720, {"force_ret": "void", "once": True}),
)


def main() -> None:
    for n, (stem, start, opts) in enumerate(MATCHES, 1):
        exe = exe_inputs(stem)
        row = next(r for r in exe.rows if r.start == start)
        c = Lifter(exe, row, {}, **opts).lift()
        view = OUT / f"view-{n}" / "src"
        if view.exists():
            shutil.rmtree(view)
        shutil.copytree(REPO_ROOT / "src", view)
        unit = view / stem / f"{row.unit}.c"
        if not unit.is_file():  # not scaffolded in the committed tree yet: scaffold in the view
            unit_row = next(u for u in exe.units if u.unit == row.unit)
            unit.write_text(
                scaffold_unit(exe.target.name, unit_row, exe.rows), encoding="utf-8", newline="\n"
            )
        text = unit.read_text(encoding="utf-8")
        marker = re.compile(rf"^INCLUDE_ASM\({re.escape(row.name)}\);$", re.M)
        assert marker.search(text), (stem, row.name, row.unit)
        body = f"\n{c.strip()}\n"
        unit.write_text(
            marker.sub(body.replace("\\", "\\\\"), text, count=1),
            encoding="utf-8",
            newline="\n",
        )
        rel = view.relative_to(REPO_ROOT).as_posix()
        print(f"view-{n}: {stem}/{row.unit} {row.name}")
        print(
            f"  docker compose run --rm -T build uv run reverseapoc check {stem}/{row.unit} "
            f"--src {rel}"
        )
        print(
            f"  docker compose run --rm -T build uv run reverseapoc lint {rel}/{stem}/{row.unit}.c"
        )
        print(f"  uv run reverseapoc readlint {rel}/{stem}/{row.unit}.c --src {rel}")


if __name__ == "__main__":
    main()

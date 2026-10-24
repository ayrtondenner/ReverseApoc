"""Capstone function discovery on the real executables (SPL-02, D-07).

These tests run only where orig/NAME exists (conftest.ORIG_DIR, or the REVERSEAPOC_ORIG override
pointing at a main checkout's orig/); each target skips on its own when its file is absent, and
they never run in CI because the game files are never committed. They assert on addresses and
counts only, never on bytes, so a failure never prints game code.

The bounds come from the research's naive estimate (05-RESEARCH Pattern 3: 1,880 / 1,837 starts,
693,162 / 688,933 decoded bytes, MEDIUM); they only guard against a broken pass. The committed
functions.csv drift test is the exact pin.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest

from conftest import ORIG_DIR, REPO_ROOT, requires_capstone
from reverseapoc.discover import Discovery, discover
from reverseapoc.le import LE
from reverseapoc.libmatch import read_runtime_csv

EXES = ("UFO2P.EXE", "TACP.EXE")  # the two game executables split in phase 5
MIN_STARTS, MAX_STARTS = 1_400, 2_500
MIN_DECODED = 600_000
_OBJ_EXECUTABLE = 0x0004  # LE object flag: executable

PARAMS = [
    pytest.param(
        name,
        id=name,
        marks=pytest.mark.skipif(
            not (ORIG_DIR / name).is_file(),
            reason=f"orig/{name} not present (run uv run reverseapoc ingest)",
        ),
    )
    for name in EXES
]


def runtime_starts(name: str) -> list[int]:
    path = REPO_ROOT / "config" / Path(name).stem.lower() / "runtime.csv"
    return [row.start for row in read_runtime_csv(path)] if path.is_file() else []


@cache
def run(name: str) -> tuple[LE, Discovery]:
    le = LE(ORIG_DIR / name)
    return le, discover(le, runtime_starts=runtime_starts(name))


@pytest.fixture(params=PARAMS)
def real(request):
    requires_capstone()
    return run(request.param)


def code_object(le: LE):
    (code,) = [obj for obj in le.objects if obj.flags & _OBJ_EXECUTABLE]
    return code


def test_entry_point_is_a_start(real):
    le, found = real
    kinds = found.evidence.get(le.entry_va, frozenset())
    assert "entry" in kinds


def test_starts_lie_in_the_code_object(real):
    le, found = real
    code = code_object(le)
    outside = sum(1 for va in found.starts if not code.contains(va))
    in_order = list(found.starts) == sorted(set(found.starts))
    assert outside == 0
    assert in_order


def test_counts_in_range(real):
    le, found = real
    starts, decoded, size = len(found.starts), found.decoded_bytes, code_object(le).vsize
    assert MIN_STARTS <= starts <= MAX_STARTS
    assert MIN_DECODED <= decoded <= size

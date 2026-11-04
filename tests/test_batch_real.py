"""batch.py against the real EXEs and the real Watcom 10.6: the judge's control and mutant.

The control: every function config/<exe>/status.csv marks matched judges exact from its
committed unit src/<exe>/<unit>.c under the unit's committed cflags rule, compiled by one
compile_batch and judged by batch.judge. It proves the batch path (gate once, thread pool,
check's relocation check and byte compare) agrees with `gate` on every match we hold.

The mutant: the first committed unit (in sorted order) whose `extern int` turned into
`extern short` breaks one of its matched functions must judge not exact. It proves the judge
can fail, so the control's "all exact" does not come from a judge that passes everything.

The verbs end to end: `reverseapoc judge` and `reverseapoc batch` on one matched function, and
`reverseapoc batch` on a clean-room draft that is not exact, so a real object gets a class.

These tests skip unless orig/UFO2P.EXE and orig/TACP.EXE, capstone, a compiler runner and every
Watcom version config/cflags.txt names are present and the gate accepts them. They write only
under build/test-batch/ (the compiler refuses objects outside the repository, so pytest's
tmp_path cannot be used) and assert on addresses, counts and booleans, never on bytes.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from conftest import (
    ORIG_DIR,
    REPO_ROOT,
    WATCOM_DIR,
    requires_capstone,
    requires_runner,
    requires_version,
)
from reverseapoc import batch, classify
from reverseapoc.cflags import Rule, load_cflags
from reverseapoc.check import ExeInputs
from reverseapoc.cli import main
from reverseapoc.compiler import CompilerError, check_gate
from reverseapoc.status import MATCHED, read_status, status_path

EXES = ("UFO2P.EXE", "TACP.EXE")
CONFIG = REPO_ROOT / "config"
BUILD_ROOT = REPO_ROOT / "build" / "test-batch"
JUDGED = ("ufo2p", 0x000108E0, "u_000105d0")  # a matched function under the `*` rule
MUTATION = (re.compile(r"\bextern int\b"), "extern short")
NOT_EXACT = "int confirm_flag_set(void) { return 1234; }\n"  # clean-room, under JUDGED's name


def _require() -> list[Rule]:
    for name in EXES:
        if not (ORIG_DIR / name).is_file():
            pytest.skip(f"orig/{name} not present (run uv run reverseapoc ingest)")
    requires_capstone()
    requires_runner()
    rules = load_cflags()
    for version in sorted({rule.version for rule in rules}):
        requires_version(version)
        try:
            check_gate("wcc386", version, watcom_dir=WATCOM_DIR)
        except CompilerError as exc:
            pytest.skip(f"Watcom {version}: gate refused ({exc})")
    return rules


def _fresh(*parts: str) -> Path:
    path = BUILD_ROOT.joinpath(*parts)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


@dataclass(frozen=True)
class Matched:
    stem: str
    unit: str
    start: int


@dataclass(frozen=True)
class Control:
    rules: list[Rule]
    exes: dict[str, ExeInputs]
    matched: list[Matched]
    result: batch.BatchResult
    objects: dict[tuple[str, str], Path]  # (stem, unit) -> its control object


def _matched(stems) -> list[Matched]:
    return [Matched(stem, row.unit, row.start) for stem in sorted(stems)
            for row in read_status(status_path(CONFIG, stem)) if row.status == MATCHED]  # fmt: skip


@pytest.fixture(scope="module")
def control() -> Control:
    rules = _require()
    exes = {}
    for name in EXES:
        exe = batch.load_exe_inputs(name, orig_dir=ORIG_DIR)
        exes[exe.stem] = exe
    matched = _matched(exes)
    units = sorted({(m.stem, m.unit) for m in matched})
    base = _fresh("control")
    objects = {(stem, unit): base / stem / f"{unit}.obj" for stem, unit in units}
    jobs = [batch.Job(REPO_ROOT / "src" / stem / f"{unit}.c", objects[stem, unit],
                      batch.committed_rule(rules, stem, unit)) for stem, unit in units]  # fmt: skip
    result = batch.compile_batch(jobs, 8, watcom_dir=WATCOM_DIR)
    return Control(rules, exes, matched, result, objects)


def test_control_every_matched_function_judges_exact(control):
    failed = [c.job.src.name for c in control.result.compiled if not c.ok]
    assert failed == []
    misses = []
    for m in control.matched:
        verdict = batch.judge(control.exes[m.stem], control.objects[m.stem, m.unit], m.start)
        if not verdict.exact:
            misses.append(f"{m.stem} 0x{m.start:08X}: {verdict.key}")
    assert misses == []
    assert len(control.matched) > 0
    print(f"control: {len(control.matched)} matched functions exact")


def _mutants(control: Control):
    """(stem, unit, mutated text) per committed matched unit holding `extern int`, sorted."""
    pattern, repl = MUTATION
    for stem, unit in sorted(control.objects):
        text = (REPO_ROOT / "src" / stem / f"{unit}.c").read_text(encoding="ascii")
        if not pattern.search(text):
            continue
        yield stem, unit, pattern.sub(repl, text, count=1)


def test_mutant_extern_int_to_short_fails_the_judge(control):
    base = _fresh("mutant")
    for stem, unit, text in _mutants(control):
        src = base / stem / f"{unit}.c"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(text, encoding="ascii")
        rule = batch.committed_rule(control.rules, stem, unit)
        job = batch.Job(src, src.with_suffix(".obj"), rule)
        (compiled,) = batch.compile_batch([job], 1, watcom_dir=WATCOM_DIR).compiled
        if not compiled.ok:
            continue
        starts = [m.start for m in control.matched if (m.stem, m.unit) == (stem, unit)]
        verdicts = [batch.judge(control.exes[stem], job.obj, start) for start in starts]
        if all(v.exact for v in verdicts):
            continue  # the mutation reached no matched function; try the next unit
        print(f"mutant {stem}/{unit}: {sum(not v.exact for v in verdicts)} of {len(verdicts)} "
              "matched functions fail")  # fmt: skip
        return
    pytest.fail("no extern int -> extern short mutant made a matched function fail")


def _roots() -> list[str]:
    return ["--orig", str(ORIG_DIR), "--watcom-dir", str(WATCOM_DIR)]


def test_judge_and_batch_verbs_end_to_end(control):
    stem, start, unit = JUDGED
    source = REPO_ROOT / "src" / stem / f"{unit}.c"
    assert main(["judge", stem, f"0x{start:08X}", str(source), *_roots()]) == 0
    root = _fresh("batchdir")
    (root / stem).mkdir()
    shutil.copyfile(source, root / stem / f"f_{start:08x}.c")
    out = BUILD_ROOT / "batch.jsonl"
    out.unlink(missing_ok=True)
    assert main(["batch", str(root), "--out", str(out), *_roots()]) == 0
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    (record,) = [r for r in records if r["address"] == f"0x{start:08X}"]
    assert (record["cell"], record["compiled"], record["exact"]) == ("committed", True, True)


def test_batch_classes_a_real_object_that_is_not_exact(control, monkeypatch):
    stem, start, _unit = JUDGED
    monkeypatch.setattr(batch, "BUILD_ROOT", BUILD_ROOT)
    root = _fresh("notexact")
    (root / stem).mkdir()
    (root / stem / f"f_{start:08x}.c").write_text(NOT_EXACT, encoding="ascii")
    out = BUILD_ROOT / "notexact.jsonl"
    out.unlink(missing_ok=True)
    assert main(["batch", str(root), "--out", str(out), *_roots()]) == 0
    (record,) = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert (record["compiled"], record["exact"]) == (True, False)
    assert record["key"] != "not defined"  # the object held the function, so both bytes were read
    assert record["class"] in classify.CLASSES
    print(f"not exact: class {record['class']}, route {record['route']}")

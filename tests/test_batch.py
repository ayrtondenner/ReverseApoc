"""batch.py, the batch compile-and-judge harness ported from spikes 010/011.

The compile tests inject a fake gate and a fake runner, so no compiler runs: they pin that the
gate runs once per (compiler, version), that each argv is compiler.build_argv's, that every
output directory exists before the pool starts and that a failed compile never leaves an object
to judge. The diff, filler and pad tests decode clean-room instruction encodings written here
(mov eax, imm32; ret; nop; mov r, r; lea r, [r]), never game bytes.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from relocpair import filler_pair, our_object, table
from reverseapoc import batch, compiler
from reverseapoc.cflags import CflagsError, Rule
from reverseapoc.x86 import decode_one

FLAGS = ("-4r", "-s", "-fpi")
RULE_106 = Rule("*", "wcc386", "10.6", FLAGS, 1)
RULE_105 = Rule("*", "wcc386", "10.5", FLAGS, 1)
ENVIRON = {"PATH": "C:/bin", "SYSTEMROOT": "C:/Windows", "TEMP": "C:/t", "SECRET": "nope"}

VA = 0x1000
MOV_EAX_1_RET = bytes.fromhex("b801000000c3")  # mov eax, 1; ret
MOV_EAX_2_RET = bytes.fromhex("b802000000c3")  # mov eax, 2; ret
IMM_FIELD = range(VA + 1, VA + 5)  # the imm32 of mov eax, imm32


class FakeGate:
    """compiler.check_gate's shape: records each (compiler, version) it is asked for."""

    def __init__(self, watcom: Path) -> None:
        self.watcom = watcom
        self.calls: list[tuple[str, str]] = []

    def __call__(self, name: str, version: str) -> compiler.Gate:
        self.calls.append((name, version))
        return compiler.Gate(version, self.watcom / version, (), f"fake {version}")


class FakeRun:
    """subprocess.run's shape. Writes the -fo= object unless `write` is False and exits with
    `returncode`; `on_first` runs before the first call does anything."""

    def __init__(self, root: Path, *, returncode: int = 0, write: bool = True, on_first=None):
        self.root = root
        self.returncode = returncode
        self.write = write
        self.on_first = on_first
        self.calls: list[tuple[list[str], dict]] = []
        self._lock = threading.Lock()

    def __call__(self, argv, **kwargs):
        with self._lock:
            first = not self.calls
            self.calls.append((list(argv), kwargs))
        if first and self.on_first is not None:
            self.on_first()
        obj = next(a for a in argv if a.startswith("-fo="))[len("-fo=") :]
        if self.write:
            (self.root / obj.replace("\\", "/")).write_bytes(b"OBJ")
        return subprocess.CompletedProcess(argv, self.returncode, "out\n", "err\n")


def _jobs(root: Path, specs) -> list[batch.Job]:
    """One Job per (directory, name, rule), its source written, its object beside it."""
    jobs = []
    for directory, name, rule in specs:
        src = root / "src" / f"{name}.c"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("int f(void) { return 0; }\n", encoding="ascii")
        jobs.append(batch.Job(src, root / "build" / directory / f"{name}.obj", rule))
    return jobs


def _compile(root: Path, jobs, run, *, workers: int = 4, gate=None):
    gate = gate if gate is not None else FakeGate(root / "watcom")
    result = batch.compile_batch(
        jobs, workers, root=root, watcom_dir=root / "watcom", gate=gate, run=run,
        platform="win32", environ=ENVIRON,
    )  # fmt: skip
    return result, gate


def test_compile_batch_gates_once_per_version(tmp_path):
    rules = (RULE_106, RULE_105, RULE_106, RULE_105, RULE_106)
    jobs = _jobs(tmp_path, [("o", f"f{i}", rule) for i, rule in enumerate(rules)])
    run = FakeRun(tmp_path)
    result, gate = _compile(tmp_path, jobs, run)
    assert gate.calls == [("wcc386", "10.5"), ("wcc386", "10.6")]
    assert len(run.calls) == 5
    assert [c.job for c in result.compiled] == jobs


def test_compile_batch_argv_env_and_cwd_are_the_wrappers(tmp_path):
    jobs = _jobs(tmp_path, [("a", "one", RULE_106), ("b", "two", RULE_105)])
    run = FakeRun(tmp_path)
    _compile(tmp_path, jobs, run, workers=1)
    watcom = tmp_path / "watcom"
    expected = {}
    for job in jobs:
        version = job.rule.version
        expected[job.src.name] = compiler.build_argv(
            watcom / version / compiler.COMPILER_EXE,
            job.rule,
            compiler.guest_path(job.src, tmp_path, inside=True),
            compiler.guest_path(job.obj, tmp_path, inside=True),
            compiler.guest_path(job.obj.with_suffix(".err"), tmp_path, inside=True),
            compiler._include_list(tmp_path, watcom, version),
            prefix=compiler.runner_prefix("win32"),
        )
    env = compiler.scrubbed_env(ENVIRON, "win32")
    assert "SECRET" not in env
    for argv, kwargs in run.calls:
        name = Path(argv[-2].replace("\\", "/")).name
        assert argv == expected[name]
        assert kwargs["cwd"] == tmp_path
        assert kwargs["env"] == env
        assert kwargs["check"] is False


def test_compile_batch_makes_every_output_directory_before_the_pool(tmp_path):
    jobs = _jobs(tmp_path, [("d1", "a", RULE_106), ("d2", "b", RULE_106), ("d3", "c", RULE_106)])
    seen = []
    run = FakeRun(
        tmp_path, on_first=lambda: seen.extend(job.obj.parent.is_dir() for job in jobs)
    )
    result, _ = _compile(tmp_path, jobs, run, workers=1)
    assert seen == [True, True, True]
    assert all(c.ok for c in result.compiled)


def test_compile_batch_failed_compile_leaves_no_object(tmp_path):
    jobs = _jobs(tmp_path, [("o", "stale", RULE_106), ("o", "partial", RULE_106)])
    jobs[0].obj.parent.mkdir(parents=True)
    jobs[0].obj.write_bytes(b"STALE")
    stale_only = FakeRun(tmp_path, returncode=1, write=False)
    result, _ = _compile(tmp_path, jobs[:1], stale_only)
    assert result.compiled[0].ok is False
    assert not jobs[0].obj.exists()
    wrote_then_failed = FakeRun(tmp_path, returncode=1, write=True)
    result, _ = _compile(tmp_path, jobs[1:], wrote_then_failed)
    assert result.compiled[0].ok is False
    assert not jobs[1].obj.exists()


def test_compile_batch_ok_result_order_and_timing(tmp_path):
    jobs = _jobs(tmp_path, [("o", f"f{i}", RULE_106) for i in range(6)])
    result, _ = _compile(tmp_path, jobs, FakeRun(tmp_path), workers=3)
    assert [c.job for c in result.compiled] == jobs
    for c in result.compiled:
        assert c.ok is True
        assert c.seconds >= 0
        assert c.output == "out\nerr\n"
        assert c.job.obj.is_file()
    assert result.gate_s >= 0
    assert result.compile_wall_s >= 0


@pytest.mark.parametrize("workers", [0, -1])
def test_compile_batch_refuses_bad_workers_before_anything(tmp_path, workers):
    jobs = _jobs(tmp_path, [("o", "a", RULE_106)])
    run, gate = FakeRun(tmp_path), FakeGate(tmp_path / "watcom")
    with pytest.raises(batch.BatchError, match="workers"):
        _compile(tmp_path, jobs, run, workers=workers, gate=gate)
    assert gate.calls == [] and run.calls == []


def test_compile_batch_refuses_two_jobs_naming_one_object(tmp_path):
    (job,) = _jobs(tmp_path, [("o", "a", RULE_106)])
    other = batch.Job(job.src.with_name("b.c"), job.obj, RULE_105)
    run, gate = FakeRun(tmp_path), FakeGate(tmp_path / "watcom")
    with pytest.raises(batch.BatchError, match="object"):
        _compile(tmp_path, [job, other], run, gate=gate)
    assert gate.calls == [] and run.calls == []
    assert not job.obj.parent.exists()


# ---- diff summary ----


def test_diff_summary_identical_code():
    assert batch.diff_summary(MOV_EAX_1_RET, MOV_EAX_1_RET, VA, set()) == (100.0, "")


def test_diff_summary_names_the_first_differing_shape():
    score, key = batch.diff_summary(MOV_EAX_1_RET, MOV_EAX_2_RET, VA, set())
    assert score < 100.0
    assert key == "mov eax, N | mov eax, N"
    assert not any(ch.isdigit() for ch in key)


def test_diff_summary_masks_relocated_fields():
    assert batch.diff_summary(MOV_EAX_1_RET, MOV_EAX_2_RET, VA, set(IMM_FIELD)) == (100.0, "")


# ---- source refusal ----


@pytest.mark.parametrize(
    "text",
    [
        "#pragma aux x\nint f(void) { return 0; }\n",
        "# pragma aux x\n",
        "int f(void) { _asm { nop } return 0; }\n",
        "int f(void) { __asm nop; return 0; }\n",
    ],
)
def test_refusal_names_pragma_and_inline_asm(text):
    reason = batch.refusal(text)
    assert reason


def test_refusal_accepts_plain_c89():
    text = "extern int g_count;\nint f(int a)\n{\n    return a + g_count;\n}\n"
    assert batch.refusal(text) is None


# ---- filler, pad and cells ----

RET_TAIL = bytes.fromhex("31c0c3")  # xor eax, eax; ret


def _insn(hex_bytes: str):
    insn = decode_one(bytes.fromhex(hex_bytes), VA)
    assert insn is not None and insn.size == len(hex_bytes) // 2
    return insn


@pytest.mark.parametrize(
    "encoding",
    ["90", "89c0", "8bc0", "89db", "8d4000", "8d00", "8d1b"],
)
def test_alignment_filler(encoding):
    assert batch.is_alignment_filler(_insn(encoding)) is True


@pytest.mark.parametrize(
    "encoding",
    [
        "89c1",  # mov ecx, eax
        "8b00",  # mov eax, dword ptr [eax]: a load
        "8d4004",  # lea eax, [eax + 4]
        "c3",  # ret
    ],
)
def test_not_alignment_filler(encoding):
    assert batch.is_alignment_filler(_insn(encoding)) is False


@pytest.mark.parametrize(
    ("tail", "expected"),
    [("8d4000", True), ("89db", True), ("", False), ("89c1", False)],
)
def test_ends_in_filler(tail, expected):
    assert batch.ends_in_filler(RET_TAIL + bytes.fromhex(tail), VA) is expected


def test_ends_in_filler_empty_code():
    assert batch.ends_in_filler(b"", VA) is False


def test_filler_tail():
    code = RET_TAIL + bytes.fromhex("8d400090")
    assert batch.filler_tail(code, VA, len(RET_TAIL)) is True
    assert batch.filler_tail(code, VA, len(code)) is False  # no tail at all
    mixed = RET_TAIL + bytes.fromhex("9089c1")
    assert batch.filler_tail(mixed, VA, len(RET_TAIL)) is False


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        (("-4r", "-ot", "-s", "-fpi"), True),
        (("-4r", "-oneatx", "-s", "-fpi"), True),
        (("-4r", "-s", "-fpi"), False),
        (("-4r", "-ox", "-s", "-fpi"), False),
    ],
)
def test_aligns_functions(flags, expected):
    assert batch.aligns_functions(flags) is expected


@pytest.mark.parametrize(
    ("tail", "flags", "expected"),
    [
        ("8d4000", ("-4r", "-oneatx", "-s", "-fpi"), True),
        ("8d4000", ("-4r", "-s", "-fpi"), False),
        ("", ("-4r", "-ot", "-s", "-fpi"), False),
        ("", ("-4r", "-s", "-fpi"), False),
    ],
)
def test_needs_pad(tail, flags, expected):
    assert batch.needs_pad(RET_TAIL + bytes.fromhex(tail), VA, flags) is expected


def test_pad_source_appends_a_non_empty_function():
    text = "int f(void)\n{\n    return 1;\n}\n"
    padded = batch.pad_source(text)
    assert batch.PAD_NAME == "reverseapoc_pad"
    assert batch.PAD_RETURN == 0x5A5A5A5A
    assert padded.startswith(text)
    tail = padded[len(text) :]
    assert f"int {batch.PAD_NAME}(void)" in tail
    assert "return 0x5a5a5a5a;" in tail
    assert batch.refusal(padded) is None


def test_cell_rule_keeps_the_base_spec():
    base = Rule("src/ufo2p/u_00000000.c", "wcc386", "10.6", FLAGS, 7)
    cell = batch.cell_rule(base, "-4r -oneatx -s -fpi")
    assert (cell.glob, cell.compiler, cell.version) == (base.glob, "wcc386", "10.6")
    assert cell.flags == ("-4r", "-oneatx", "-s", "-fpi")


@pytest.mark.parametrize("text", ["-fo=x.obj", "-i=foo", "-4r -s-ifoo", "-4r /x"])
def test_cell_rule_refuses_wrapper_owned_and_unsafe_flags(text):
    with pytest.raises((CflagsError, batch.BatchError)):
        batch.cell_rule(RULE_106, text)


@pytest.mark.parametrize("text", ["", "   "])
def test_cell_rule_refuses_a_blank_cell(text):
    with pytest.raises(batch.BatchError):
        batch.cell_rule(RULE_106, text)


def _compiled(ok: bool, output: str = "") -> batch.Compiled:
    job = batch.Job(Path("a.c"), Path("a.obj"), RULE_106)
    return batch.Compiled(job, ok, 0.1, output)


def test_cell_record_of_a_judged_cell():
    verdict = batch.Verdict(True, True, True, 0, 11, 11, 100.0, "")
    record = batch.cell_record("ufo2p", 0x108E0, "committed", RULE_106, _compiled(True), verdict)
    assert record == {
        "exe": "ufo2p", "address": "0x000108E0", "cell": "committed", "flags": "-4r -s -fpi",
        "compiled": True, "exact": True, "exact_trim": False, "score": 100.0, "len": [11, 11],
        "key": "",
    }  # fmt: skip


def test_cell_record_of_a_failed_compile():
    output = "a.c(3): Error! E1011: Symbol 'x' has not been declared\nother\n"
    verdict = batch.unjudged(11)
    record = batch.cell_record("tacp", 0x10, "-4r -ot -s -fpi", RULE_106, _compiled(False, output),
                               verdict)  # fmt: skip
    assert record["compiled"] is False and record["exact"] is False
    assert record["score"] == 0.0 and record["len"] == [0, 11]
    assert record["key"] == "compile failed: a.c(3): Error! E1011: Symbol 'x' has not been declared"


def test_cell_record_of_a_refused_source():
    record = batch.cell_record("tacp", 0x10, "committed", RULE_106, None, batch.unjudged(4),
                               key="refused: '#pragma'")  # fmt: skip
    assert record["compiled"] is False and record["key"] == "refused: '#pragma'"


def test_check_cells_refuses_an_empty_rule_list_and_a_bad_cell():
    with pytest.raises(batch.BatchError, match="no rule"):
        batch.check_cells([], ["-4r -ox -s -fpi"])
    with pytest.raises(CflagsError):
        batch.check_cells([RULE_106], ["-4r -fo=x.obj"])
    batch.check_cells([RULE_106], ["-4r -ox -s -fpi"])


# ---- judge on original trailing filler (07-48) --------------------------------------------------


def _judged(tmp_path: Path, pair):
    """batch.judge of `pair`: our body as an OMF object on disk, the original as ExeInputs."""
    symbols = table(pair.row)
    obj = tmp_path / "f.obj"
    obj.write_bytes(our_object(pair.ours, publics=[(symbols.linker_name(pair.row.start), 0)]))
    exe = SimpleNamespace(rows=(pair.row,), flat=pair.orig.flat, fixups=tuple(pair.orig.fixups),
                          symbols=symbols, target=SimpleNamespace(name="SYNTH.EXE"))  # fmt: skip
    return batch.judge(exe, obj, pair.row.start)


def test_judge_refused_tail_is_not_exact_but_exact_trim(tmp_path):
    verdict = _judged(tmp_path, filler_pair(shift=1))  # the row end off 16-byte alignment
    assert verdict.exact is False
    assert verdict.exact_trim is True


def test_judge_exact_on_a_filler_pair(tmp_path):
    verdict = _judged(tmp_path, filler_pair())
    assert verdict.exact is True
    assert verdict.exact_trim is False
    assert verdict.len_ours < verdict.len_row


def test_with_source_names_the_path_and_lf_sha256(tmp_path):
    """07-48c: a record names the C it judged, so `flags propose --from-batch` can find it: a
    repo-relative POSIX path inside the repo (absolute outside), and the text's LF sha256."""
    import hashlib

    verdict = batch.Verdict(True, True, True, 0, 11, 11, 100.0, "")
    record = batch.cell_record("ufo2p", 0x108E0, "committed", RULE_106, _compiled(True), verdict)
    text = "int f(void)\r\n{\r\n    return 0;\r\n}\r\n"
    lf = hashlib.sha256(text.replace("\r\n", "\n").encode("ascii")).hexdigest()
    inside = batch.REPO_ROOT / "build" / "batch" / "in" / "ufo2p" / "f_000108e0.c"
    named = batch.with_source(record, inside, text)
    assert named == {**record, "source": "build/batch/in/ufo2p/f_000108e0.c",
                     "source_sha256": lf}  # fmt: skip
    outside = tmp_path / "f_000108e0.c"
    assert batch.with_source(record, outside, text.replace("\r\n", "\n"))["source"] == (
        outside.resolve().as_posix())  # fmt: skip
    assert batch.with_source(record, outside, None)["source_sha256"] == ""
    assert "source" not in record  # the record itself is unchanged

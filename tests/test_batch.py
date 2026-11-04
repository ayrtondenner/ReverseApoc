"""batch.py, the batch compile-and-judge harness ported from spikes 010/011.

The compile tests inject a fake gate and a fake runner, so no compiler runs: they pin that the
gate runs once per (compiler, version), that each argv is compiler.build_argv's, that every
output directory exists before the pool starts and that a failed compile never leaves an object
to judge. The diff, filler and pad tests decode clean-room instruction encodings written here
(mov eax, imm32; ret; nop; mov r, r; lea r, [r]), never game bytes.
"""

from __future__ import annotations

import dataclasses
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from relocpair import filler_pair, our_object, table
from reverseapoc import batch, compiler
from reverseapoc.cflags import CflagsError, Rule
from reverseapoc.check import Defined
from reverseapoc.functions import FunctionRow
from reverseapoc.omf import OMFFixup, Segment
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


# ---- the stack mask (07.1, D-01: it ranks, it decides nothing) ----------------------------------
#
# Clean-room encodings, written here. The bodies with a prologue and an epilogue are the shape
# real rows have (R5): push, sub esp, an esp operand, add esp, pop, ret.

PUSH_EBX, POP_EBX, RET = "53", "5b", "c3"
SUB_ESP_10, SUB_ESP_14 = "83ec10", "83ec14"
ADD_ESP_10, ADD_ESP_14 = "83c410", "83c414"
LOAD_EAX_ESP, LOAD_EAX_ESP_4, LOAD_EAX_ESP_8, LOAD_EAX_ESP_C = (
    "8b0424", "8b442404", "8b442408", "8b44240c"
)  # fmt: skip
LOAD_ECX_ESP, LOAD_ECX_ESP_4 = "8b0c24", "8b4c2404"


def _code(*parts: str) -> bytes:
    return bytes.fromhex("".join(parts))


def _both_scores(ours: bytes, theirs: bytes) -> tuple[float, float]:
    """(raw score, stack score) of one pair at VA, nothing relocated."""
    raw, _key = batch.diff_summary(ours, theirs, VA, set())
    return raw, batch.stack_score(ours, theirs, VA, set())


def test_stack_mask_equalises_esp_displacements():
    raw, stack = _both_scores(_code(LOAD_EAX_ESP_8, RET), _code(LOAD_EAX_ESP_C, RET))
    assert raw < 100.0
    assert stack == 100.0


def test_stack_mask_equalises_the_frame_size():
    raw, stack = _both_scores(_code(SUB_ESP_10, RET), _code(SUB_ESP_14, RET))
    assert raw < 100.0
    assert stack == 100.0


def test_stack_mask_equalises_the_frame_release():
    raw, stack = _both_scores(_code(ADD_ESP_10, RET), _code(ADD_ESP_14, RET))
    assert raw < 100.0
    assert stack == 100.0


def test_stack_mask_normalises_a_bare_esp_operand():
    """`[esp]` is slot 0: it compares equal to `[esp + N]`."""
    raw, stack = _both_scores(_code(LOAD_EAX_ESP, RET), _code(LOAD_EAX_ESP_8, RET))
    assert raw < 100.0
    assert stack == 100.0


def test_stack_mask_covers_a_negative_displacement():
    raw, stack = _both_scores(_code("8b4424fc", RET), _code(LOAD_EAX_ESP_8, RET))  # [esp - 4]
    assert raw < 100.0
    assert stack == 100.0


def test_stack_mask_on_a_full_prologue_and_epilogue():
    ours = _code(PUSH_EBX, SUB_ESP_10, LOAD_EAX_ESP_8, ADD_ESP_10, POP_EBX, RET)
    theirs = _code(PUSH_EBX, SUB_ESP_14, LOAD_EAX_ESP_C, ADD_ESP_14, POP_EBX, RET)
    raw, stack = _both_scores(ours, theirs)
    assert raw < 100.0
    assert stack == 100.0


def test_stack_mask_on_a_slot_swap_with_slot_zero():
    ours = _code(PUSH_EBX, SUB_ESP_10, LOAD_EAX_ESP, LOAD_ECX_ESP_4, ADD_ESP_10, POP_EBX, RET)
    theirs = _code(PUSH_EBX, SUB_ESP_10, LOAD_EAX_ESP_4, LOAD_ECX_ESP, ADD_ESP_10, POP_EBX, RET)
    raw, stack = _both_scores(ours, theirs)
    assert raw < 100.0
    assert stack == 100.0


def test_stack_mask_on_a_prologue_still_sees_a_different_instruction():
    ours = _code(PUSH_EBX, SUB_ESP_10, LOAD_EAX_ESP_8, ADD_ESP_10, POP_EBX, RET)
    theirs = _code(PUSH_EBX, SUB_ESP_10, LOAD_ECX_ESP_4, ADD_ESP_10, POP_EBX, RET)
    assert batch.stack_score(ours, theirs, VA, set()) < 100.0


def test_stack_mask_keeps_the_index_register():
    ours = _code("8b448c08", RET)  # mov eax, [esp + ecx*4 + 8]
    assert batch.stack_score(ours, _code("8b448c0c", RET), VA, set()) == 100.0
    assert batch.stack_score(ours, _code("8b048c", RET), VA, set()) == 100.0  # [esp + ecx*4]
    assert batch.stack_score(ours, _code("8b449408", RET), VA, set()) < 100.0  # edx*4


def test_stack_mask_on_a_relocated_store_to_a_bare_esp_operand():
    """An instruction with a relocated field is shown as its shape: the bare `[esp]` of that
    shape still compares equal to `[esp + N]`."""
    ours = _code("c7042400000000", RET)  # mov dword ptr [esp], imm32
    theirs = _code("c744240800000000", RET)  # mov dword ptr [esp + 8], imm32
    masked = set(range(VA + 3, VA + 7))  # inside either store, and short of the ret after it
    assert batch.stack_score(ours, theirs, VA, masked) == 100.0


MOV_EAX_ESP, LEA_EAX_ESP_4, LEA_ECX_ESP_4 = "89e0", "8d442404", "8d4c2404"
MOV_EBP_ESP, LEA_EBP_ESP_4 = "89e5", "8d6c2404"
MOV_ESP_ESP = "89e4"


def test_stack_mask_reads_a_copy_of_esp_as_the_address_of_slot_0():
    """Watcom takes the address of slot 0 with `mov r, esp`, not `lea r, [esp]`."""
    ours = _code(SUB_ESP_10, MOV_EAX_ESP, "e800000000", ADD_ESP_10, RET)
    theirs = _code(SUB_ESP_10, LEA_EAX_ESP_4, "e800000000", ADD_ESP_10, RET)
    raw, stack = _both_scores(ours, theirs)
    assert raw < 100.0
    assert stack == 100.0


def test_stack_mask_keeps_the_register_of_a_copy_of_esp():
    ours, theirs = _code(MOV_EAX_ESP, RET), _code(LEA_ECX_ESP_4, RET)
    assert batch.stack_score(ours, theirs, VA, set()) < 100.0


@pytest.mark.parametrize("copy", [MOV_EBP_ESP, MOV_ESP_ESP], ids=["ebp", "esp"])
def test_stack_mask_leaves_a_copy_that_is_no_address(copy):
    """`mov ebp, esp` opens a frame, and `mov esp, esp` is filler: neither takes slot 0."""
    raw, stack = _both_scores(_code(copy, RET), _code(LEA_EBP_ESP_4, RET))
    assert stack == raw


FRAMED = (PUSH_EBX, "55", MOV_EBP_ESP, SUB_ESP_10)  # push ebx; push ebp; mov ebp, esp; sub esp, N
UNFRAMED = (PUSH_EBX, "55", SUB_ESP_10)
UNFRAMED_LEAVE = (ADD_ESP_10, "5d", POP_EBX, RET)  # add esp, N; pop ebp; pop ebx; ret
FRAMED_LEAVE = ("89ec", "5d", POP_EBX, RET)  # mov esp, ebp; pop ebp; pop ebx; ret


def _ebp_local(slot: int) -> str:
    """mov eax, dword ptr [ebp - slot]"""
    return f"8b45{256 - slot:02x}"


def test_stack_mask_equalises_ebp_locals_when_mov_ebp_esp_opens_the_body():
    ours = _code(*FRAMED, _ebp_local(8), *FRAMED_LEAVE)
    theirs = _code(*FRAMED, _ebp_local(0xC), *FRAMED_LEAVE)
    raw, stack = _both_scores(ours, theirs)
    assert raw < 100.0
    assert stack == 100.0


def test_stack_mask_keeps_the_index_register_of_an_ebp_local():
    ours = _code(*FRAMED, "8b448df8", *FRAMED_LEAVE)  # mov eax, [ebp + ecx*4 - 8]
    assert batch.stack_score(ours, _code(*FRAMED, "8b448df4", *FRAMED_LEAVE), VA, set()) == 100.0
    other = _code(*FRAMED, "8b4495f8", *FRAMED_LEAVE)  # edx*4
    assert batch.stack_score(ours, other, VA, set()) < 100.0


def test_stack_mask_leaves_an_argument_of_an_ebp_frame():
    """`[ebp + N]` is a stack argument, not a local: its offset is not the frame's to choose."""
    ours = _code(*FRAMED, "8b4508", *FRAMED_LEAVE)  # mov eax, [ebp + 8]
    raw, stack = _both_scores(ours, _code(*FRAMED, "8b450c", *FRAMED_LEAVE))
    assert stack == raw


def test_stack_mask_leaves_ebp_as_a_general_register():
    """`-4r` code uses ebp freely: with no `mov ebp, esp` to open the body, `[ebp - N]` stays."""
    ours = _code(*UNFRAMED, _ebp_local(8), *UNFRAMED_LEAVE)
    raw, stack = _both_scores(ours, _code(*UNFRAMED, _ebp_local(0xC), *UNFRAMED_LEAVE))
    assert raw < 100.0
    assert stack == raw


def test_stack_mask_leaves_ebp_after_a_late_copy_of_esp():
    """A `mov ebp, esp` behind anything but saved registers does not open the body."""
    late = (LOAD_EAX_ESP_8, MOV_EBP_ESP)
    ours = _code(*late, _ebp_local(8), RET)
    raw, stack = _both_scores(ours, _code(*late, _ebp_local(0xC), RET))
    assert raw < 100.0
    assert stack == raw


def test_stack_mask_touches_nothing_else():
    other_base = _both_scores(_code("8b4308", RET), _code("8b430c", RET))  # [ebx + N]
    other_add = _both_scores(_code("83c310", RET), _code("83c314", RET))  # add ebx, N
    other_sub = _both_scores(_code("83eb10", RET), _code("83eb14", RET))  # sub ebx, N
    immediates = _both_scores(MOV_EAX_1_RET, MOV_EAX_2_RET)
    for raw, stack in (other_base, other_add, other_sub, immediates):
        assert raw < 100.0
        assert stack == raw


def test_cell_record_keys_are_unchanged():
    """A guard: the stack score is a Verdict field, and the JSONL of `batch` and `judge` keeps
    its keys."""
    record = batch.cell_record("tacp", 0x10, "committed", RULE_106, _compiled(True),
                               batch.unjudged(4))  # fmt: skip
    assert list(record) == ["exe", "address", "cell", "flags", "compiled", "exact", "exact_trim",
                            "score", "len", "key"]  # fmt: skip


def test_verdict_stack_score_defaults_after_exact_trim():
    assert batch.unjudged(4).stack_score == 0.0
    names = [field.name for field in dataclasses.fields(batch.Verdict)]
    assert names[-2:] == ["exact_trim", "stack_score"]


def test_judge_fills_the_stack_score_and_keeps_the_raw_score(tmp_path):
    body = _code(PUSH_EBX, SUB_ESP_10, LOAD_EAX_ESP_8, ADD_ESP_10, POP_EBX, RET)
    other = _code(PUSH_EBX, SUB_ESP_14, LOAD_EAX_ESP_C, ADD_ESP_14, POP_EBX, RET)
    verdict = _judged(tmp_path, filler_pair(b"", body=other, ours=body))
    assert verdict.exact is False
    assert verdict.score < 100.0
    assert verdict.stack_score == 100.0


# ---- the function body: the failure keys of judge and the key that dedupes a search -------------


def _synth_exe(pair) -> SimpleNamespace:
    return SimpleNamespace(rows=(pair.row,), flat=pair.orig.flat, fixups=tuple(pair.orig.fixups),
                           symbols=table(pair.row),
                           target=SimpleNamespace(name="SYNTH.EXE"))  # fmt: skip


def test_function_body_holds_the_defined_function(tmp_path):
    pair = filler_pair()
    exe = _synth_exe(pair)
    obj = tmp_path / "f.obj"
    obj.write_bytes(our_object(pair.ours, publics=[(exe.symbols.linker_name(pair.row.start), 0)]))
    body = batch.function_body(exe, obj, pair.row.start)
    assert body.defined.row == pair.row
    assert body.defined.ours == pair.ours
    assert pair.row in body.rows


def test_function_body_names_a_missing_object(tmp_path):
    pair = filler_pair()
    found = batch.function_body(_synth_exe(pair), tmp_path / "missing.obj", pair.row.start)
    assert found.startswith("no object: ")
    verdict = batch.judge(_synth_exe(pair), tmp_path / "missing.obj", pair.row.start)
    assert (verdict.exact, verdict.key) == (False, found)
    assert (verdict.differing, verdict.len_ours, verdict.score) == (-1, 0, 0.0)


def test_function_body_names_an_undefined_function(tmp_path):
    pair = filler_pair()
    obj = tmp_path / "f.obj"
    obj.write_bytes(our_object(pair.ours, publics=[("other_", 0)]))
    assert batch.function_body(_synth_exe(pair), obj, pair.row.start) == "not defined"
    assert batch.judge(_synth_exe(pair), obj, pair.row.start).key == "not defined"


def _fixup(offset: int, name: str = "_D_00020004", displacement: int = 0) -> OMFFixup:
    return OMFFixup(offset, 4, True, 9, 1, 2, "extern", 1, name, displacement)


def _body(data: bytes, fixups: tuple[OMFFixup, ...] = (), *, off: int = 0,
          size: int | None = None):  # fmt: skip
    """A FunctionBody of `size` bytes at `off` in one code segment holding `data` and `fixups`."""
    segment = Segment(1, "_TEXT", "CODE", len(data), True, data, fixups)
    row = FunctionRow(0x1000, 0x1010, "func_00001000", "game", "unit", "call")
    size = len(data) - off if size is None else size
    return batch.FunctionBody(None, (row,), Defined(row, "f_", segment, off, size))


def test_body_key_is_equal_for_equal_bytes_and_relocations():
    data = bytes(16)
    assert batch.body_key(_body(data, (_fixup(4),))) == batch.body_key(_body(data, (_fixup(4),)))


def test_body_key_reads_the_bytes():
    assert batch.body_key(_body(bytes(16))) != batch.body_key(_body(bytes(15) + b"\x01"))


def test_body_key_tells_equal_bytes_that_relocate_differently():
    data = bytes(16)
    base = batch.body_key(_body(data, (_fixup(4),)))
    assert base != batch.body_key(_body(data, (_fixup(8),)))
    assert base != batch.body_key(_body(data, (_fixup(4, "_D_00020008"),)))
    assert base != batch.body_key(_body(data, (_fixup(4, displacement=4),)))
    assert base != batch.body_key(_body(data))


def test_body_key_takes_fixup_offsets_from_the_function():
    data = bytes(32)
    first = _body(data, (_fixup(4),), off=0, size=16)
    second = _body(data, (_fixup(20),), off=16, size=16)
    assert batch.body_key(first) == batch.body_key(second)


def test_body_key_skips_a_fixup_outside_the_function():
    data = bytes(32)
    alone = _body(data, off=0, size=16)
    with_neighbour = _body(data, (_fixup(16), _fixup(20)), off=0, size=16)
    assert batch.body_key(alone) == batch.body_key(with_neighbour)


# ---- the slot map (07.1, D-01: it reports, it decides nothing) ----------------------------------
#
# Clean-room encodings, written here. A frame opens with a saved register and `sub esp, N` (R9).

PUSH_EAX, PUSH_ECX, POP_ECX = "50", "51", "59"
CALL = "e800000000"
ADD_ESP_4 = "83c404"
FRAME = (PUSH_EBX, SUB_ESP_10)
LEAVE = (ADD_ESP_10, POP_EBX, RET)


def _load(slot: int) -> str:
    """mov eax, dword ptr [esp + slot]"""
    return f"8b4424{slot:02x}"


def _load_ecx(slot: int) -> str:
    """mov ecx, dword ptr [esp + slot]"""
    return f"8b4c24{slot:02x}"


def _slots(ours: bytes, theirs: bytes, masked: frozenset[int] = frozenset()) -> batch.SlotMap:
    return batch.slot_map(ours, theirs, VA, set(masked))


def test_slot_map_pairs_aligned_esp_operands():
    assert _slots(_code(LOAD_EAX_ESP_8), _code(LOAD_EAX_ESP_C)).pairs == ((8, 0xC),)


def test_slot_map_keeps_a_slot_that_matches():
    assert _slots(_code(LOAD_EAX_ESP_8), _code(LOAD_EAX_ESP_8)).pairs == ((8, 8),)


def test_slot_map_reads_a_bare_esp_operand_as_slot_0():
    assert _slots(_code(LOAD_EAX_ESP), _code(LOAD_EAX_ESP_4)).pairs == ((0, 4),)


def test_slot_map_reads_an_indexed_operand():
    ours, theirs = _code("8b448c08"), _code("8b448c0c")  # mov eax, [esp + ecx*4 + 8], then + 0xc
    assert _slots(ours, theirs).pairs == ((8, 0xC),)


def test_slot_map_reads_a_relocated_store():
    """The immediate is relocated, so the two stores align whatever it holds."""
    ours = _code("c7042400100000")  # mov dword ptr [esp], 0x1000
    theirs = _code("c744240400200000")  # mov dword ptr [esp + 4], 0x2000
    masked = frozenset({VA + 3, VA + 4, VA + 5, VA + 6, VA + 7})
    assert _slots(ours, theirs, masked).pairs == ((0, 4),)


def test_slot_map_reads_a_copy_of_esp_as_slot_0():
    ours = _code(*FRAME, MOV_EAX_ESP, *LEAVE)
    theirs = _code(*FRAME, LEA_EAX_ESP_4, *LEAVE)
    assert _slots(ours, theirs).pairs == ((0, 4),)


def test_slot_map_follows_a_pushed_argument_to_a_copy_of_esp():
    ours = _code(*FRAME, PUSH_EAX, MOV_EAX_ESP, CALL, *LEAVE)
    theirs = _code(*FRAME, PUSH_EAX, "8d442408", CALL, *LEAVE)  # lea eax, [esp + 8]
    assert _slots(ours, theirs).pairs == ((-4, 4),)


@pytest.mark.parametrize("copy", [MOV_EBP_ESP, MOV_ESP_ESP], ids=["ebp", "esp"])
def test_slot_map_leaves_a_copy_that_is_no_address(copy):
    assert _slots(_code(*FRAME, copy, *LEAVE), _code(*FRAME, copy, *LEAVE)).pairs == ()


def test_slot_map_reads_an_ebp_local_as_a_slot():
    ours = _code(*FRAMED, _ebp_local(8), *FRAMED_LEAVE)
    theirs = _code(*FRAMED, _ebp_local(0xC), *FRAMED_LEAVE)
    assert _slots(ours, theirs).pairs == ((-8, -0xC),)


def test_slot_map_reads_the_frame_size_of_an_ebp_frame():
    slots = _slots(_code(*FRAMED, *FRAMED_LEAVE), _code(*FRAMED, *FRAMED_LEAVE))
    assert (slots.frame_ours, slots.frame_theirs) == (0x10, 0x10)


def test_slot_map_does_not_shift_an_ebp_local_by_a_push():
    """A push moves esp, never ebp."""
    ours = _code(*FRAMED, PUSH_EAX, _ebp_local(8), CALL, *FRAMED_LEAVE)
    theirs = _code(*FRAMED, PUSH_EAX, _ebp_local(0xC), CALL, *FRAMED_LEAVE)
    assert _slots(ours, theirs).pairs == ((-8, -0xC),)


def test_slot_map_skips_ebp_as_a_general_register():
    ours = _code(*UNFRAMED, _ebp_local(8), *UNFRAMED_LEAVE)
    assert _slots(ours, ours).pairs == ()


def test_slot_map_skips_other_base_registers():
    assert _slots(_code("8b4308"), _code("8b430c")).pairs == ()  # mov eax, [ebx + 8], then + 0xc


def test_slot_map_follows_a_pushed_argument():
    """The saved register before `sub esp, N` shifts nothing: depth starts at the frame (R9)."""
    ours = _code(*FRAME, _load(8), PUSH_EAX, _load_ecx(0xC), CALL, *LEAVE)
    theirs = _code(*FRAME, _load(0xC), PUSH_EAX, _load_ecx(0x10), CALL, *LEAVE)
    assert _slots(ours, theirs).pairs == ((8, 0xC),)


def test_slot_map_reads_a_pushed_slot_before_the_push_moves_esp():
    push_slot = "ff742408"  # push dword ptr [esp + 8]
    ours = _code(*FRAME, push_slot, push_slot, CALL, *LEAVE)
    theirs = _code(*FRAME, "ff74240c", "ff74240c", CALL, *LEAVE)
    assert _slots(ours, theirs).pairs == ((4, 8), (8, 0xC))


@pytest.mark.parametrize("cleanup", [(), (ADD_ESP_4,)], ids=["callee pops", "caller cleans"])
def test_slot_map_returns_to_the_frame_after_a_call(cleanup):
    def body(slot: int) -> bytes:
        return _code(*FRAME, _load(slot), PUSH_ECX, CALL, *cleanup, _load(slot), *LEAVE)

    assert _slots(body(8), body(0xC)).pairs == ((8, 0xC),)


def test_slot_map_follows_a_pop():
    """`push` and `pop` with no call between them, as a small constant is loaded."""

    def body(slot: int) -> bytes:
        return _code(*FRAME, _load(slot), PUSH_EAX, POP_ECX, _load(slot), *LEAVE)

    assert _slots(body(8), body(0xC)).pairs == ((8, 0xC),)


def test_slot_map_reports_a_bijection():
    ours = _code(*FRAME, _load(8), _load_ecx(0xC), *LEAVE)
    theirs = _code(*FRAME, _load(0xC), _load_ecx(8), *LEAVE)
    slots = _slots(ours, theirs)
    assert slots.pairs == ((8, 0xC), (0xC, 8))
    assert slots.bijection is True


def test_slot_map_reports_a_conflict():
    """One of our slots on two of theirs: slot sharing or a different frame, not a permutation."""
    ours = _code(*FRAME, _load(8), _load_ecx(8), *LEAVE)
    theirs = _code(*FRAME, _load(8), _load_ecx(0xC), *LEAVE)
    slots = _slots(ours, theirs)
    assert slots.pairs == ((8, 8), (8, 0xC))
    assert slots.bijection is False


def test_slot_map_reports_two_of_our_slots_on_one_of_theirs():
    ours = _code(*FRAME, _load(8), _load_ecx(0xC), *LEAVE)
    theirs = _code(*FRAME, _load(8), _load_ecx(8), *LEAVE)
    assert _slots(ours, theirs).bijection is False


def test_slot_map_reports_both_frame_sizes():
    ours = _code(PUSH_EBX, SUB_ESP_10, _load(8), ADD_ESP_10, POP_EBX, RET)
    theirs = _code(PUSH_EBX, SUB_ESP_14, _load(8), ADD_ESP_14, POP_EBX, RET)
    slots = _slots(ours, theirs)
    assert (slots.frame_ours, slots.frame_theirs) == (0x10, 0x14)


def test_slot_map_gives_a_body_with_no_frame_size_0():
    slots = _slots(_code(RET), _code(SUB_ESP_10, ADD_ESP_10, RET))
    assert (slots.frame_ours, slots.frame_theirs) == (0, 0x10)
    assert slots.pairs == ()
    assert slots.bijection is True


def test_function_slots_reads_our_object_against_the_row(tmp_path):
    pair = filler_pair(b"", body=_code(SUB_ESP_14, _load(0xC), ADD_ESP_14, RET),
                       ours=_code(SUB_ESP_10, _load(8), ADD_ESP_10, RET))  # fmt: skip
    exe = _synth_exe(pair)
    obj = tmp_path / "f.obj"
    obj.write_bytes(our_object(pair.ours, publics=[(exe.symbols.linker_name(pair.row.start), 0)]))
    slots = batch.function_slots(exe, obj, pair.row.start)
    assert slots.pairs == ((8, 0xC),)
    assert (slots.frame_ours, slots.frame_theirs) == (0x10, 0x14)


def test_function_slots_of_a_missing_object_still_reads_the_row(tmp_path):
    pair = filler_pair(b"", body=_code(SUB_ESP_14, _load(0xC), ADD_ESP_14, RET))
    slots = batch.function_slots(_synth_exe(pair), tmp_path / "missing.obj", pair.row.start)
    assert slots.pairs == ()
    assert (slots.frame_ours, slots.frame_theirs) == (0, 0x14)

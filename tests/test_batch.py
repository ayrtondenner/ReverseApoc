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

import pytest

from reverseapoc import batch, compiler
from reverseapoc.cflags import Rule

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

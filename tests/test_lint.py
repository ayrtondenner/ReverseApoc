"""The C89 lint gate (SPL-12, D-14): clang -fsyntax-only with the Watcom compat header.

The argv, the missing-clang refusal and the verb run on the host with a fake runner. The clang
tests need clang-18 or clang (the container) and the compat-header test the Watcom 10.6 tree and
a compiler runner; each skips naming what is missing. Sources are made-up C written to tmp_path
or build/test-lint/ (gitignored); no game bytes.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_clang, requires_runner, requires_version
from reverseapoc import lint
from reverseapoc.cli import main as cli_main
from reverseapoc.compiler import CompilerError, check_gate, compile_source
from reverseapoc.lint import LINT_FLAGS, LintError, collect_sources, run_lint

EXPECTED_FLAGS = (
    "-fsyntax-only",
    "-std=gnu89",
    "-Werror=declaration-after-statement",
    "--target=i386-unknown-none",
    "-ffreestanding",
    "-nostdinc",
    "-funsigned-char",
    "-D__386__",
    "-D__FLAT__",
    "-D__WATCOMC__=1060",
    "-Iinclude",
    "-include",
    "include/watcom_compat.h",
)
FAKE_CLANG = "/usr/bin/clang-18"


class FakeRunner:
    """Records each argv and its keyword arguments; returns a fixed exit code."""

    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.calls: list[tuple[list[str], dict]] = []
        self.returncode = returncode
        self.stderr = stderr

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        return subprocess.CompletedProcess(argv, self.returncode, "", self.stderr)


@pytest.fixture
def fake_clang(monkeypatch):
    names = {"clang-18": FAKE_CLANG}
    monkeypatch.setattr(lint.shutil, "which", lambda name, *a, **k: names.get(name))


def _source(path: Path, text: str = "int f(void);\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")
    return path


def test_lint_flags_are_the_d14_command():
    assert LINT_FLAGS == EXPECTED_FLAGS
    assert lint.WATCOMC_VALUE == "1060"
    assert lint.CLANGD_FLAGS == EXPECTED_FLAGS[1:]


def test_lint_argv(tmp_path, fake_clang):
    path = _source(tmp_path / "a.c")
    runner = FakeRunner()
    result = run_lint([path], runner=runner)
    assert result.ok
    assert result.files == (path,)
    [(argv, kwargs)] = runner.calls
    assert argv == [FAKE_CLANG, *EXPECTED_FLAGS, str(path)]
    assert kwargs["cwd"] == REPO_ROOT  # -Iinclude and -include are relative to the repo root


def test_lint_reports_a_failing_file(tmp_path, fake_clang):
    path = _source(tmp_path / "a.c")
    result = run_lint([path], runner=FakeRunner(1, "a.c:3:5: error: boom"))
    assert not result.ok
    assert "error: boom" in result.output
    assert "FAILED" in result.format()


def test_lint_without_clang(tmp_path, monkeypatch):
    monkeypatch.setattr(lint.shutil, "which", lambda *a, **k: None)
    with pytest.raises(LintError, match="docker compose run --rm build uv run reverseapoc lint"):
        run_lint([_source(tmp_path / "a.c")], runner=FakeRunner())


def test_collect_sources(tmp_path):
    b = _source(tmp_path / "src" / "ufo2p" / "b.c")
    a = _source(tmp_path / "src" / "ufo2p" / "a.c")
    _source(tmp_path / "src" / "ufo2p" / "notes.txt")
    single = _source(tmp_path / "one.c")
    # *.c under directories, files as given, sorted, each once
    assert collect_sources([tmp_path / "src", single, a]) == sorted([a, b, single])


def test_collect_sources_refuses_a_missing_path(tmp_path):
    with pytest.raises(LintError, match="not found"):
        collect_sources([tmp_path / "nope"])


def test_lint_verb_with_no_sources(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(lint.shutil, "which", lambda *a, **k: None)  # no clang is needed
    assert cli_main(["lint", str(tmp_path)]) == 0
    assert "0 files" in capsys.readouterr().out


def test_lint_verb_writes_the_stamp_only_when_ok(tmp_path, fake_clang, monkeypatch):
    path = _source(tmp_path / "a.c")
    stamp = tmp_path / "stamps" / "lint.stamp"
    monkeypatch.setattr(lint, "_default_runner", FakeRunner(1, "error"))
    assert cli_main(["lint", str(path), "--stamp", str(stamp)]) == 1
    assert not stamp.exists()
    monkeypatch.setattr(lint, "_default_runner", FakeRunner(0))
    assert cli_main(["lint", str(path), "--stamp", str(stamp)]) == 0
    assert stamp.is_file()


def test_lint_verb_without_clang_names_the_container(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(lint.shutil, "which", lambda *a, **k: None)
    assert cli_main(["lint", str(_source(tmp_path / "a.c"))]) == 1
    assert "docker compose run --rm build uv run reverseapoc lint" in capsys.readouterr().err


# ---- with clang (the container) ----

WATCOM_CONSTRUCTS = """\
/* Watcom constructs the compat header must let through (D-14) */
#include "common.h"

#if __WATCOMC__ != 1060
#error "__WATCOMC__ is not 10.6"
#endif

int __watcall f(int);
#pragma aux f parm [eax] value [eax] modify [ecx edx];
void __far __interrupt g(void);
int __cdecl h(char __near *p);

INCLUDE_ASM(func_00010000);

int func_00010010(int x)
{
    int y;

    y = x + 1;
    return y;
}
"""

MIXED_DECLARATION = """\
int func_00010020(int x)
{
    x = x + 1;
    int y = x;
    return y;
}
"""


def test_lint_passes_watcom_constructs(tmp_path):
    requires_clang()
    result = run_lint([_source(tmp_path / "unit.c", WATCOM_CONSTRUCTS)])
    assert result.ok, result.output


def test_lint_fails_a_mixed_declaration(tmp_path):
    requires_clang()
    result = run_lint([_source(tmp_path / "unit.c", MIXED_DECLARATION)])
    assert not result.ok
    assert "mixing declarations and code" in result.output


# ---- the compat header is inert for wcc386 ----

LINT_ROOT = REPO_ROOT / "build" / "test-lint"
VERSION = "10.6"
PLAIN = """\
int func_00012345(int x)
{
    return x + 1;
}
"""


def test_compat_header_is_inert_for_watcom(request):
    requires_runner()
    requires_version(VERSION)
    root = LINT_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", request.node.name)
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    try:
        check_gate("wcc386", VERSION, watcom_dir=WATCOM_DIR, stamps=root / "stamps")
    except CompilerError as exc:
        pytest.skip(f"Watcom {VERSION}: gate refused ({exc})")
    sha1s = []
    for name, text in (("plain.c", PLAIN), ("compat.c", '#include "watcom_compat.h"\n' + PLAIN)):
        src = _source(root / name, text)
        result = compile_source(
            src,
            src.with_suffix(".obj"),
            root=REPO_ROOT,
            watcom_dir=WATCOM_DIR,
            log=root / "cc.log",
            stamps=root / "stamps",
        )
        assert result.ok, result.output
        sha1s.append(result.normalized_sha1)
    assert sha1s[0] is not None
    assert sha1s[0] == sha1s[1]

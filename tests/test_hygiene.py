"""Bring-your-own-files hygiene: game files and the compiler never reach the image, and the
container cannot write to them."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc.cflags import parse_cflags
from reverseapoc.targets import load_manifest
from reverseapoc.watcom import load_watcom_manifest

# Every host directory that holds user-supplied, never-committed bytes.
PROTECTED_DIRS = ("orig", "third_party")


def _ignore_patterns(path: Path) -> set[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


@pytest.mark.parametrize("ext", ["exe", "EXE", "iso", "ISO", "bin", "BIN"])
def test_dockerignore_excludes_executables_and_disc_images_at_any_depth(ext):
    # A bare `*.exe` in .dockerignore only matches at the context root; `**/` matches anywhere.
    assert f"**/*.{ext}" in _ignore_patterns(REPO_ROOT / ".dockerignore")


@pytest.mark.parametrize("name", PROTECTED_DIRS)
def test_dockerignore_excludes_protected_dirs(name):
    assert f"{name}/" in _ignore_patterns(REPO_ROOT / ".dockerignore")


def _compose_volumes() -> list[tuple[str, str, str]]:
    """(host, container, mode) for every short-syntax bind mount in docker/compose.yaml."""
    text = (REPO_ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
    mounts = []
    for m in re.finditer(r"^\s*-\s+(\.\.[^\s:]*):(/[^\s:]+)(?::(\w+))?\s*$", text, re.M):
        mounts.append((m.group(1), m.group(2), m.group(3) or "rw"))
    return mounts


def test_compose_parses_the_repo_mount():
    assert ("..", "/work", "rw") in _compose_volumes()


@pytest.mark.parametrize("name", PROTECTED_DIRS)
def test_protected_dir_is_read_only_at_its_own_path_inside_the_repo_mount(name):
    # The repo is mounted read-write at /work, so /work/<name> exposes the host directory
    # writable unless a read-only mount sits exactly on that path (or on a parent below /work).
    ro_targets = {target for _, target, mode in _compose_volumes() if mode == "ro"}
    assert f"/work/{name}" in ro_targets


def test_every_mount_of_a_protected_dir_is_read_only():
    for host, target, mode in _compose_volumes():
        if any(host == f"../{d}" or host.startswith(f"../{d}/") for d in PROTECTED_DIRS):
            assert mode == "ro", f"{host} -> {target} is mounted {mode}"


def _live_docs() -> list[Path]:
    # docs/research/ holds dated research snapshots and is left as written.
    docs = [p for p in (REPO_ROOT / "docs").rglob("*.md") if "research" not in p.parts]
    return [*docs, REPO_ROOT / "README.md", REPO_ROOT / "CLAUDE.md"]


def test_live_docs_carry_no_bare_tbd_markers():
    # Unknowns are written as "not known yet; <requirement or phase> records it", never "TBD".
    hits = [
        f"{path.relative_to(REPO_ROOT)}:{n}"
        for path in _live_docs()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\bTBD\b", line)
    ]
    assert not hits


def test_no_doc_mentions_a_phase_zero():
    # Milestone phases are numbered from 1 (GSD reserves the zero id); a "Phase 0" anywhere,
    # research notes and planning records included, would point at a phase that does not exist.
    docs = [*(REPO_ROOT / "docs").rglob("*.md"), *(REPO_ROOT / ".planning").rglob("*.md")]
    hits = [
        f"{path.relative_to(REPO_ROOT)}:{n}"
        for path in [*docs, REPO_ROOT / "README.md", REPO_ROOT / "CLAUDE.md"]
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\bphases? 0\b|^\| 0\. ", line, re.I)
    ]
    assert not hits


def test_toolchain_records_the_confirmed_le_layout():
    # RT-05: the LE layout section carries the spike-confirmed facts, the trailer after the last
    # page of UFO2P and TACP included, instead of the old EOF claim and the open question.
    text = (REPO_ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    stale = ("runs exactly to EOF", "To be confirmed in Phase 2/3")
    assert [claim for claim in stale if claim in text] == []
    assert [needle for needle in ("0x1A0723", "0x303DDF", "trailer") if needle not in text] == []


def test_toolchain_records_the_compiler_result():
    # CID-05: the Compiler section states the measured result (per-EXE flags table, the D-03
    # wibo log, the runtime map, the probe scan and the C/C++ scan) instead of the Phase 4
    # hypotheses and open questions.
    text = (REPO_ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    stale = (
        "To be confirmed in Phase 4",
        "to be confirmed in Phase 4",
        "is a Phase 4 spike",
        "Decoding it is Phase 4 work",
        "Not known yet; CID-05 (Phase 4) records them here",
        "To be confirmed in Phase 5:** scan obj2",
    )
    assert [claim for claim in stale if claim in text] == []
    needles = (
        "| Flag | UFO2P | TACP | Evidence | Status |",
        "04-native-vs-wibo",
        "runtime.csv",
        "probe scan",
        "cppscan",
    )
    assert [needle for needle in needles if needle not in text] == []


# Phase 5 (D-03, D-04, D-14, D-20): Ghidra 12.1.4 with the lastonesky loader runs headless in the
# Docker image, retrokit is not used, and the compat header has its path. Each phrase below was
# in a live doc before the correction (docs/research/ keeps the old wording as written).
_STALE_GHIDRA_PHRASES = (
    "Ghidra 12.1.4 + JDK 21 in WSL2",
    "WSL2 (with JDK 21)",
    "Ghidra and decomp.wtf run in WSL2",
    "WSL2: Ghidra",
    "(or retrokit), in WSL2",
    "(lastonesky or retrokit) in WSL2",
    "**Decided in Phase 5.**",
    "Its path is decided in Phase 5",
)


def test_docs_place_ghidra_in_the_image():
    hits = [
        f"{path.relative_to(REPO_ROOT)}: {phrase}"
        for path in _live_docs()
        for phrase in _STALE_GHIDRA_PHRASES
        if phrase in path.read_text(encoding="utf-8")
    ]
    assert hits == []
    style = (REPO_ROOT / "docs" / "coding-style.md").read_text(encoding="utf-8")
    assert "include/watcom_compat.h" in style
    toolchain = (REPO_ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    assert "ghidra-export" in toolchain


_SPIKE_005 = "005-objdiff-omf-elf"


def test_toolchain_records_spike_005():
    # D-01, D-02: "objdiff and the OMF bridge" links the spike record and states the verdict
    # exactly as the record's `verdict:` line, instead of "The Phase 5 spike decides".
    readme = REPO_ROOT / ".planning" / "spikes" / _SPIKE_005 / "README.md"
    verdict = re.search(r"^verdict: (\S+)$", readme.read_text(encoding="utf-8"), re.M)
    assert verdict
    text = (REPO_ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    assert "The Phase 5 spike decides" not in text
    link = f"spike [005](../.planning/spikes/{_SPIKE_005}/README.md), verdict {verdict[1]}"
    assert link in text


def _default_cflags_rule():
    """The `*` rule of config/cflags.txt, parsed against the versions of config/watcom.toml."""
    path = REPO_ROOT / "config" / "cflags.txt"
    versions = tuple(load_watcom_manifest())
    rules = parse_cflags(path.read_text(encoding="utf-8"), versions=versions, where=str(path))
    return next(rule for rule in rules if rule.glob == "*")


_RULE_EXES = ("UFO2P.EXE", "TACP.EXE")


def _normalized(text: str) -> str:
    """The text with every run of whitespace collapsed to one space."""
    return " ".join(text.split())


def _matching_rule_rows(matching: str, glob: str) -> dict[str, tuple[str, frozenset[str]]]:
    """exe -> (compiler@version, flag set) for the rows `| <glob> | <EXE> | <spec> | <flags> |`
    of docs/matching.md "Compiler and flags per module"."""
    pattern = rf"^\| {re.escape(glob)} \| (\S+\.EXE) \| (\S+) \| ([^|]+?) \|"
    rows = re.findall(pattern, matching, flags=re.MULTILINE)
    return {exe: (spec, frozenset(flags.split())) for exe, spec, flags in rows}


def _default_rule_doc_problems(rule, toolchain: str, matching: str) -> list[str]:
    """What is wrong when the `*` default rule and the docs disagree (empty = they agree).

    docs/toolchain.md must hold the whole rule text as one code span (whitespace-normalised, so
    a rule that is a prefix of the documented one, or only shares flags with it, is caught), and
    each per-EXE row of docs/matching.md must carry the same spec and the same flag set."""
    problems = []
    rule_text = _normalized(f"{rule.glob} {rule.spec} {' '.join(rule.flags)}")
    if f"`{rule_text}`" not in _normalized(toolchain):
        problems.append(f"toolchain.md does not quote the rule `{rule_text}`")
    rows = _matching_rule_rows(matching, rule.glob)
    problems += [
        f"matching.md has no `{rule.glob}` row for {exe}" for exe in _RULE_EXES if exe not in rows
    ]
    for exe, (spec, flags) in rows.items():
        if (spec, flags) != (rule.spec, frozenset(rule.flags)):
            problems.append(f"matching.md row for {exe} says {spec} {sorted(flags)}")
    return problems


def test_cflags_default_rule_is_documented():
    # CID-05: the `*` rule of config/cflags.txt appears whole in docs/toolchain.md and, per EXE,
    # in docs/matching.md, so the rule cannot drift away from the evidence the docs give.
    rule = _default_cflags_rule()
    toolchain = (REPO_ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    matching = (REPO_ROOT / "docs" / "matching.md").read_text(encoding="utf-8")
    assert _default_rule_doc_problems(rule, toolchain, matching) == []


_DRIFTED_RULES = (
    "*  wcc386@10.6  -5r -s",  # the superseded rule
    "*  wcc386@10.6  -5r -s -fpi",
    "*  wcc386@10.6  -4r -s -fpi87",  # contradicted by the EMU387 row
    "*  wcc386@10.6  -3s",
    "*  wcc386@10.6  -4r -s -zm -zp1",  # candidates, not evidence
    "*  wcc386@10.6  -4r -s -oneatx",
    "*  wcc386@10.6  -4r -s",  # a prefix of the documented rule
    "*  wcc386@11.0  -4r -s -fpi",
    "*  wcc386@10.5  -4r -s -fpi",
)


def _matching_rows(ufo2p: str, tacp: str | None) -> str:
    """A "Compiler and flags per module" table; `ufo2p` and `tacp` are `spec | flags` cells."""
    lines = [
        "| Module / file glob | EXE | Compiler@version | Flags | Evidence | Date |",
        "|---|---|---|---|---|---|",
        f"| * | UFO2P.EXE | {ufo2p} | proof | 2026-10-21 |",
    ]
    if tacp is not None:
        lines.append(f"| * | TACP.EXE | {tacp} | proof | 2026-10-21 |")
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("drifted", _DRIFTED_RULES)
def test_default_rule_doc_check_catches_a_drifted_rule(drifted):
    # The check is only worth something if it can fail: parse a rule that differs from the
    # documented one (in memory; config/cflags.txt is never touched) and expect a complaint.
    # The matching.md rows are written from the drifted rule itself, so only the toolchain.md
    # half of the check can complain here.
    versions = tuple(load_watcom_manifest())
    rule = parse_cflags(drifted, versions=versions)[0]
    cells = f"{rule.spec} | {' '.join(rule.flags)}"
    toolchain = (REPO_ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    problems = _default_rule_doc_problems(rule, toolchain, _matching_rows(cells, cells))
    assert [p for p in problems if p.startswith("toolchain.md")] != []


@pytest.mark.parametrize(
    ("ufo2p", "tacp"),
    [
        ("wcc386@10.6 | -5r -s -fpi", "wcc386@10.6 | -4r -s -fpi"),  # other flags in one row
        ("wcc386@10.6 | -4r -s -fpi", "wcc386@11.0 | -4r -s -fpi"),  # other version in one row
        ("wcc386@10.6 | -4r -s", "wcc386@10.6 | -4r -s -fpi"),  # a flag dropped in one row
    ],
)
def test_default_rule_doc_check_catches_a_drifted_matching_row(ufo2p, tacp):
    rule = _default_cflags_rule()
    toolchain = (REPO_ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    assert _default_rule_doc_problems(rule, toolchain, _matching_rows(ufo2p, tacp)) != []


def test_default_rule_doc_check_accepts_matching_rows_in_any_flag_order():
    rule = _default_cflags_rule()
    toolchain = (REPO_ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    both = "wcc386@10.6 | -fpi -s -4r"
    assert _default_rule_doc_problems(rule, toolchain, _matching_rows(both, both)) == []


def test_default_rule_doc_check_wants_a_row_per_exe():
    rule = _default_cflags_rule()
    toolchain = (REPO_ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    one_row = _matching_rows("wcc386@10.6 | -4r -s -fpi", None)
    assert _default_rule_doc_problems(rule, toolchain, one_row) != []


_HASH_PREFIX_DIGITS = 8


def _manifest_hash_needles() -> set[str]:
    """Every [[targets]] md5 and sha1 of config/targets.toml, in full and as its first eight hex
    digits. Read at test time, so no hash is written down in this file."""
    digests = [digest for t in load_manifest() for digest in (t.md5, t.sha1)]
    return {*digests, *(digest[:_HASH_PREFIX_DIGITS] for digest in digests)}


def _files_with_manifest_hashes(root: Path, needles: set[str], exclude: set[str]) -> list[str]:
    """Sorted POSIX paths, relative to `root`, of the *.py files under `root` whose text holds
    any needle (case-insensitive). Paths in `exclude` and anything under __pycache__ are
    skipped."""
    hits = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if "__pycache__" in rel.parts or rel.as_posix() in exclude:
            continue
        text = path.read_text(encoding="utf-8").lower()
        if any(needle in text for needle in needles):
            hits.append(rel.as_posix())
    return sorted(hits)


def test_manifest_hashes_scan_detects_a_planted_hash(tmp_path):
    # The guard below is only worth something if it can fail: plant a manifest SHA-1 (and,
    # separately, its 8-digit prefix) in throwaway files and expect the scan to name both.
    sha1 = load_manifest()[0].sha1
    needles = _manifest_hash_needles()
    (tmp_path / "test_full.py").write_text(f'EXPECTED = "{sha1}"\n', encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "test_prefix.py").write_text(f"# {sha1[:8]}\n", encoding="utf-8")
    (tmp_path / "test_pinned.py").write_text(f'PIN = "{sha1}"\n', encoding="utf-8")
    (tmp_path / "test_clean.py").write_text("EXPECTED = load_manifest()\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.py").write_text(f"# {sha1}\n", encoding="utf-8")
    found = _files_with_manifest_hashes(tmp_path, needles, exclude={"test_pinned.py"})
    assert found == ["sub/test_prefix.py", "test_full.py"]


# D-15: expected SHA-1s reach round-trip tests only through load_manifest, never as copied
# strings. D-21 exempts tests/test_targets.py alone: it pins the manifest itself, so an edit to
# config/targets.toml to make a gate pass still fails the suite.
def test_round_trip_tests_never_copy_manifest_hashes():
    found = _files_with_manifest_hashes(
        REPO_ROOT / "tests", _manifest_hash_needles(), exclude={"test_targets.py"}
    )
    assert found == []


def _dependency_doc_problems(pyproject_text: str, tools_text: str) -> list[str]:
    """What is wrong when a runtime dependency has no docs/tools.md reason (empty = none).

    Every `[project].dependencies` entry must be an exact `name==version` pin, and some table
    row of the tools text must hold that pin as a code span (so `foo==1.0` is not satisfied by
    `foo==1.0.1`), the name and the `**Use**` verdict."""
    problems = []
    rows = [line for line in tools_text.splitlines() if line.startswith("|")]
    for pin in tomllib.loads(pyproject_text)["project"].get("dependencies", []):
        name, sep, version = pin.partition("==")
        if not sep or not version:
            problems.append(f"{pin!r} is not an exact `name==version` pin")
            continue
        documented = any(
            f"`{pin}`" in row and name.lower() in row.lower() and "**Use**" in row for row in rows
        )
        if not documented:
            problems.append(f"docs/tools.md has no **Use** row holding `{pin}`")
    return problems


def test_every_runtime_dependency_is_documented():
    # .claude/rules/tools.md: no third-party dependency without a reason in docs/tools.md. Each
    # `[project].dependencies` pin needs a "Use" row in docs/tools.md holding the exact pin.
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    tools = (REPO_ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    assert _dependency_doc_problems(pyproject, tools) == []


_PLANTED_PYPROJECT = '[project]\nname = "x"\ndependencies = ["foo==1.0"]\n'
_TOOLS_HEADER = (
    "| Candidate | Verdict | Reason | Install method | Status |\n|---|---|---|---|---|\n"
)


def test_dependency_doc_check_catches_an_undocumented_pin():
    # The check is only worth something if it can fail: a planted pin with no row, a row with
    # another version, and a row that is not a "Use" verdict are each one problem.
    other = "| [bar](https://example.invalid) | **Use** | r | uv: `bar==2.0` | Phase 5 |\n"
    wrong_pin = "| [foo](https://example.invalid) | **Use** | r | uv: `foo==1.1` | Phase 5 |\n"
    longer_pin = "| [foo](https://example.invalid) | **Use** | r | uv: `foo==1.0.1` | Phase 5 |\n"
    skipped = "| [foo](https://example.invalid) | **Skip** | r | uv: `foo==1.0` | skipped |\n"
    for rows in (other, wrong_pin, longer_pin, skipped):
        assert len(_dependency_doc_problems(_PLANTED_PYPROJECT, _TOOLS_HEADER + rows)) == 1
    good = "| [foo](https://example.invalid) 1.0 | **Use** | r | uv: `foo==1.0` | Phase 5 |\n"
    assert _dependency_doc_problems(_PLANTED_PYPROJECT, _TOOLS_HEADER + good) == []


def test_dependency_doc_check_wants_an_exact_pin():
    loose = '[project]\nname = "x"\ndependencies = ["foo>=1.0"]\n'
    row = "| [foo](https://example.invalid) | **Use** | r | uv: `foo>=1.0` | Phase 5 |\n"
    assert len(_dependency_doc_problems(loose, _TOOLS_HEADER + row)) == 1


def _skip_message(helper) -> str:
    with pytest.raises(pytest.skip.Exception) as skipped:
        helper()
    return str(skipped.value)


def test_requires_helpers_skip_cleanly(monkeypatch, tmp_path):
    # Wave 0 skip helpers (05-03): each skips, naming what is missing, instead of failing.
    import importlib.util

    import conftest

    monkeypatch.setenv("GHIDRA_INSTALL_DIR", str(tmp_path))
    message = _skip_message(conftest.requires_ghidra)
    assert "GHIDRA_INSTALL_DIR" in message
    assert "analyzeHeadless" in message

    monkeypatch.setattr(shutil, "which", lambda *_args, **_kwargs: None)
    assert "objdiff-cli" in _skip_message(conftest.requires_objdiff)
    assert "clang" in _skip_message(conftest.requires_clang)

    monkeypatch.setattr(importlib.util, "find_spec", lambda *_args, **_kwargs: None)
    assert "capstone" in _skip_message(conftest.requires_capstone)


def test_requires_ghidra_returns_the_install_dir(monkeypatch, tmp_path):
    import conftest

    (tmp_path / "support").mkdir()
    (tmp_path / "support" / "analyzeHeadless").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("GHIDRA_INSTALL_DIR", str(tmp_path))
    assert conftest.requires_ghidra() == tmp_path


def test_gitignore_excludes_the_compiler_media_and_installs():
    patterns = _ignore_patterns(REPO_ROOT / ".gitignore")
    assert "third_party/" in patterns
    assert "/watcom/" in patterns


_FETCH_NEEDLES = ["fetch-watcom", "install-watcom", "archive.org", "watcom-media"]
_WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))


@pytest.mark.parametrize("needle", _FETCH_NEEDLES)
def test_dockerfile_never_fetches_the_compiler(needle):
    # The proprietary compiler is user-supplied at run time, never baked into an image layer.
    text = (REPO_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert needle not in text


_DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"

# D-03, D-04, D-06, D-14: Ghidra 12.1.4 and the lastonesky LE loader in their own cached stage,
# each zip pinned by SHA-256; OpenJDK 21 and clang 18 at exact apt versions.
_GHIDRA_NEEDLES = [
    "ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db",  # Ghidra 12.1.4 zip
    "0a9c65cee8c090ec4b7f72b595eb829267f80ae8f36a2a44d4ef1ef5af41be45",  # LxLoader v12.1.4-1
    "AS ghidra",
    "openjdk-21-jdk-headless=21.0.12.1+1-1~24.04.4",
    "clang-18=1:18.1.3-1ubuntu1",
    "clang=1:18.0-59~exp2",
    "GHIDRA_INSTALL_DIR=/opt/ghidra",
]


def _dockerfile_lines() -> list[str]:
    return _DOCKERFILE.read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("needle", _GHIDRA_NEEDLES)
def test_dockerfile_pins_ghidra(needle):
    assert needle in _DOCKERFILE.read_text(encoding="utf-8")


def test_dockerfile_checks_every_download():
    # T-05-26: every curl download is followed by a sha256sum check that fails the build.
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert text.count("curl -fsSL") >= 1
    assert text.count("sha256sum -c") >= text.count("curl -fsSL")


def test_dockerfile_copies_nothing_from_the_context():
    # T-05-27, D-06: only COPY --from=<stage>, never ADD, so no file of the build context
    # (orig/, third_party/, the Watcom trees) can enter an image layer.
    stripped = [line.strip() for line in _dockerfile_lines()]
    copies = [line for line in stripped if line.upper().startswith("COPY")]
    assert copies
    assert [line for line in copies if "--from=" not in line] == []
    assert [line for line in stripped if line.upper().startswith("ADD")] == []


def test_ci_workflows_exist():
    assert _WORKFLOWS


@pytest.mark.parametrize("needle", _FETCH_NEEDLES)
@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda p: p.name)
def test_ci_never_fetches_the_compiler(workflow, needle):
    # docs/legal.md: CI never downloads or installs the compiler either.
    assert needle not in workflow.read_text(encoding="utf-8")


def _git_ls_stage(path: str) -> str | None:
    """`git ls-files --stage` for `path` in this checkout, or None when there is no git or no
    work tree to ask (a source export). safe.directory=* lets a bind mount owned by another
    user be read inside the container."""
    git = shutil.which("git")
    if git is None:
        return None
    cmd = [git, "-c", "safe.directory=*", "-C", str(REPO_ROOT)]
    inside = subprocess.run([*cmd, "rev-parse", "--is-inside-work-tree"], capture_output=True)
    if inside.returncode != 0:
        return None
    listed = subprocess.run(
        [*cmd, "ls-files", "--stage", "--", path], capture_output=True, text=True, check=True
    )
    return listed.stdout


def test_commit_msg_hook_is_tracked_and_executable():
    # The Co-Authored-By hook only helps if every clone gets it, executable, via
    # `git config core.hooksPath .githooks`.
    staged = _git_ls_stage(".githooks/commit-msg")
    if staged is None:
        pytest.skip("not a git work tree")
    assert staged.split()[:1] == ["100755"]
    assert staged.rstrip().endswith("\t.githooks/commit-msg")


@pytest.mark.skipif(not Path("/.dockerenv").exists(), reason="only inside the container")
@pytest.mark.parametrize("path", ["/work/orig", "/work/third_party", "/work/watcom"])
def test_protected_paths_are_not_writable_in_the_container(path):
    if not os.path.isdir(path):
        pytest.skip(f"{path} is not mounted")
    assert not os.access(path, os.W_OK)

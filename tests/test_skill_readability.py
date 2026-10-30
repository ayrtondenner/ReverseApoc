"""The watcom-readability project skill (.claude/skills/watcom-readability/SKILL.md, plan 07-36).

The driver appends it to every readability session (D-17, D-18; plan 07-38). It must stay short,
and every path, verb, wrapper command, format and number it states must match the code: the
writing-skills RED baseline (ruling F20) showed sessions reading tools/*.py only to learn the
proposal line, the RL03 header, the waiver and the readability output, so the skill states them
and these tests keep them true."""

from __future__ import annotations

import re

from conftest import REPO_ROOT
from reverseapoc import attempt, hooks, proposals, readlint, session
from reverseapoc.check import EXIT_MISMATCH, EXIT_OK
from reverseapoc.cli import build_parser

SKILL = REPO_ROOT / ".claude" / "skills" / "watcom-readability" / "SKILL.md"
MAX_LINES = 300
SECTIONS = (  # plan 07-36 Task 1, in this order
    "What you may change",
    "Header comments",
    "Names, evidence and proposals",
    "Constants without changing bytes",
    "Readlint",
    "The attempt wrapper",
    "When to stop",
)
PATH_PREFIXES = ("docs/", "include/", "config/", "src/", ".claude/", "tools/", "tests/")
_SPAN = re.compile(r"`([^`\n]+)`")
_PLACEHOLDER = re.compile(r"<[^<>]+>|NNNN")
_VERB = re.compile(r"\breverseapoc ([a-z][a-z-]*)")
_PREFIX = " ".join(hooks.ATTEMPT_PREFIX)
_HEADING = re.compile(r"(?m)^#{2,3} (.+)$")


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n"), "SKILL.md starts with YAML frontmatter"
    block = text[4 : text.index("\n---\n", 4)]
    fields = {}
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith(" "):
            fields[key.strip()] = value.strip()
    return fields


def _headings(text: str) -> list[str]:
    """The `## ` headings outside fenced blocks."""
    headings, fenced = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
            headings.append(line[3:].strip())
    return headings


def _fenced(text: str) -> list[str]:
    """The bodies of the fenced blocks, in order."""
    return re.findall(r"(?ms)^```[a-z]*\n(.*?)^```", text)


def _spans(text: str) -> list[str]:
    return [span.strip() for span in _SPAN.findall(text)]


def _section(text: str, title: str) -> str:
    start = text.index(f"\n## {title}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def test_skill_is_short_and_shaped():
    text = _text()
    assert len(text.splitlines()) <= MAX_LINES
    fields = _frontmatter(text)
    assert fields["name"] == "watcom-readability"
    assert fields["description"].startswith("Use when")
    assert tuple(_headings(text)) == SECTIONS


def _repo_path(span: str) -> str | None:
    """The repo-relative path a backticked span names, without an anchor or trailing
    punctuation; None when the span is not a path under PATH_PREFIXES."""
    if not span.startswith(PATH_PREFIXES) or " " in span:
        return None
    path = re.split(r"[#:]", span, maxsplit=1)[0]
    return path.rstrip(".,;)")


def _slug(heading: str) -> str:
    kept = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return kept.replace(" ", "-")


def test_skill_paths_and_anchors_exist():
    spans = [span for span in _spans(_text()) if _repo_path(span)]
    assert spans, "the skill links to docs for depth"
    for span in spans:
        path = _repo_path(span)
        assert list(REPO_ROOT.glob(_PLACEHOLDER.sub("*", path))), f"{path} names nothing"
        if "#" in span:
            anchor = span.split("#", 1)[1].rstrip(".,;)")
            heads = _HEADING.findall((REPO_ROOT / path).read_text(encoding="utf-8"))
            assert anchor in {_slug(h) for h in heads}, span


def test_skill_verbs_exist():
    found = set(_VERB.findall(_text()))
    sub = next(a for a in build_parser()._actions if a.dest == "command")
    assert "attempt" in found
    assert found <= set(sub.choices), sorted(found - set(sub.choices))


def test_skill_commands_are_the_wrapper_forms():
    """Every `uv run ...` span is ATTEMPT_PREFIX plus one of hooks.ATTEMPT_FORMS, every short
    `attempt ...` span is a form, and every form is quoted."""
    quoted = set()
    for span in _spans(_text()):
        tokens = span.split()
        if span.startswith("uv run"):
            assert span.startswith(_PREFIX + " "), f"{span!r} is not an attempt wrapper command"
        if "attempt" not in tokens:
            continue
        argv = tuple(tokens[tokens.index("attempt") + 1 :])
        assert argv in hooks.ATTEMPT_FORMS or hooks.attempt_form_matches(argv), span
        if span.startswith(_PREFIX + " "):
            quoted.add(argv)
    assert set(hooks.ATTEMPT_FORMS) <= quoted, "every wrapper form is quoted in full"


def test_skill_names_the_required_terms():
    text = _text()
    assert "proposals.jsonl" in text and "/* lit:" in text
    for kind in proposals.EVIDENCE_KINDS:
        assert f"{kind}:" in text, kind
    for rule in ("RL01", "RL02", "RL03", "RL04", "RL05", "RL06"):
        assert rule in _section(text, "Readlint"), rule
    assert hooks.UNIT_FILE_ENV in text and hooks.PROPOSALS_ENV in text


# ---- the formats, checked against the code that parses them (RED: "read source to learn") ----


def _proposal_lines(text: str) -> list[str]:
    return [line for block in _fenced(text) for line in block.splitlines()
            if line.startswith('{"op": ')]  # fmt: skip


def test_example_proposals_parse_and_pass_the_name_and_header_rules():
    lines = _proposal_lines(_text())
    parsed = [proposals.parse_line(line, n) for n, line in enumerate(lines, start=1)]
    renames = [p for p in parsed if isinstance(p, proposals.Rename)]
    headers = [p for p in parsed if isinstance(p, proposals.Header)]
    assert renames and headers, "one rename and one header example"
    for rename in renames:
        assert proposals.name_problem(rename.name) is None, rename
    for header in headers:
        assert proposals.header_problem(header) is None, header


def _header_example(text: str) -> str:
    """The first comment in a fenced block that holds an `Address:` line."""
    for block in _fenced(text):
        if " * Address: " in block:
            return block[block.index("/*") : block.index("*/") + 2]
    raise AssertionError("no RL03 header example")


def test_example_header_passes_rl03():
    header = _header_example(_text())
    lines = readlint._comment_lines(header)
    name = lines[0].split(":", 1)[0]
    address = next(line for line in lines if line.startswith(readlint.ADDRESS))
    exe_file, start = address.removeprefix(readlint.ADDRESS).split()
    exe = exe_file.removesuffix(".EXE").lower()
    assert exe in proposals.EXES
    names = {name: int(start, 16)}
    assert list(readlint._header_problems(lines, name, exe, names)) == []


def test_header_template_spells_the_exe_files():
    """RED item 9: `Address: UFO2P 0x...` fails RL03; the EXE file name is required."""
    text = _text()
    assert "Address: <UFO2P.EXE|TACP.EXE> 0x%08X" in text
    assert "Evidence: <string|table|call|vocab>: <text>" in text


def test_every_waiver_in_the_skill_is_a_readlint_waiver():
    waivers = re.findall(r"/\* lit:.*?\*/", _text())
    assert waivers
    for waiver in waivers:
        assert readlint.WAIVER.fullmatch(waiver), waiver


def _example_lint() -> attempt.Lint:
    """The readlint half the skill's output example shows: one failing RL01 on a callee, three
    pending renames (counted per hit, not per name) and one waiver."""
    unit = "src/ufo2p/u_00012340.c"
    why = "is a placeholder name: name it (a D-19 rename)"
    fail = readlint.Violation(unit, 15, "RL01", f"func_00012400 {why}")
    pending = tuple(attempt.Pending(readlint.Violation(unit, line, "RL01", f"D_000A1230 {why}"),
                                    "clock_frame_fraction")
                    for line in (4, 16, 19))  # fmt: skip
    result = readlint.ReadlintResult(
        files_checked=(unit,), waivers={unit: 1}, allowlisted={unit: 0},
        violations=(fail, *(p.violation for p in pending)),
    )  # fmt: skip
    return attempt.Lint(result, failing=(fail,), pending=pending)


def test_output_example_is_the_real_format():
    """RED item 6: the skill shows the readability check's real summary lines."""
    text = _text()
    assert attempt._READABILITY_VERDICT[EXIT_MISMATCH] in text
    assert attempt._CHECK_HALF[EXIT_OK].strip() in text
    for line in _example_lint().lines():
        assert line in text, line
    assert "rename proposal refused: " in text


# ---- the numbers and the planned driver behaviour ----


def test_skill_states_the_budgets_from_the_code():
    text = _text()
    assert f"{attempt.CHECK_BUDGET} checks" in text
    assert f"{session.MAX_TURNS} turns" in text
    assert str(hooks.CHECK_TIMEOUT_MS) in text and "run_in_background" in text
    assert "90 s" not in text, "no unmeasured per-check figure (watcom-decomp M1)"
    assert "elapsed" in text
    assert str(proposals.EVIDENCE_TEXT_MAX) in text and str(proposals.NAME_MAX) in text


def test_skill_states_what_lands_and_marks_it_planned():
    """RED item 8 and ruling F18: the final view text lands, names are re-checked at landing,
    and driver behaviour not built yet is said to be planned."""
    stop = _section(_text(), "When to stop")
    assert "checks/NNNN.c" in stop and "byte-identical" in stop
    assert "planned" in stop
    for outcome in ("LANDED", "PARTIAL", "REFUSED"):
        assert outcome in stop, outcome
    names = _section(_text(), "Names, evidence and proposals")
    assert "re-checked at landing" in names and "last" in names

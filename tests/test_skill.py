"""The watcom-decomp project skill (.claude/skills/watcom-decomp/SKILL.md, AGT-09, D-19).

The skill rides in the system prompt of every matching session, so it must stay short and every
path, verb and command it names must exist: a stale name costs the agent a turn. Commands are
checked against hooks.ATTEMPT_FORMS (ruling F27), the only Bash a matching session may run."""

from __future__ import annotations

import re
from pathlib import Path

from conftest import REPO_ROOT
from reverseapoc import hooks, session
from reverseapoc.cli import build_parser

SKILL = REPO_ROOT / ".claude" / "skills" / "watcom-decomp" / "SKILL.md"
MAX_LINES = 300  # D-19
SECTIONS = (  # D-19's nine sections, in its order
    "Calling convention and linker names",
    "Flags",
    "C89 and the lint",
    "Pragmas",
    "Relocation rules",
    "Strings, statics and jump tables",
    "Replacing INCLUDE_ASM",
    "The attempt wrapper",
    "When to give up",
)
PATH_PREFIXES = ("docs/", "include/", "config/", "src/", ".claude/", "tools/", "tests/")
_SPAN = re.compile(r"`([^`\n]+)`")
_PLACEHOLDER = re.compile(r"<[^<>]+>|NNNN")
_VERB = re.compile(r"\breverseapoc ([a-z][a-z-]*)")
_PREFIX = " ".join(hooks.ATTEMPT_PREFIX)


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


def _spans(text: str) -> list[str]:
    return [span.strip() for span in _SPAN.findall(text)]


def test_skill_is_short_and_shaped():
    text = _text()
    assert len(text.splitlines()) <= MAX_LINES
    fields = _frontmatter(text)
    assert fields["name"] == "watcom-decomp"
    assert fields["description"].startswith("Use when")
    assert tuple(_headings(text)) == SECTIONS


def _repo_path(span: str) -> str | None:
    """The repo-relative path a backticked span names, without an anchor, a `:L12` line suffix
    or trailing punctuation; None when the span is not a path under PATH_PREFIXES."""
    if not span.startswith(PATH_PREFIXES) or " " in span:
        return None
    path = re.split(r"[#:]", span, maxsplit=1)[0]
    return path.rstrip(".,;)")


def test_skill_paths_exist():
    paths = [path for span in _spans(_text()) if (path := _repo_path(span))]
    assert paths, "the skill links to docs for depth (D-19)"
    for path in paths:
        pattern = _PLACEHOLDER.sub("*", path)
        assert list(REPO_ROOT.glob(pattern)), f"{path} names nothing in the repository"


def _verbs() -> set[str]:
    sub = next(a for a in build_parser()._actions if a.dest == "command")
    return set(sub.choices)


def test_skill_verbs_exist():
    found = set(_VERB.findall(_text()))
    assert "attempt" in found
    assert found <= _verbs(), sorted(found - _verbs())


def _commands(text: str) -> list[list[str]]:
    """The argv after ATTEMPT_PREFIX of every backticked span that starts `uv run`."""
    commands = []
    for span in _spans(text):
        if not span.startswith("uv run"):
            continue
        assert span.startswith(_PREFIX + " "), f"{span!r} is not an attempt wrapper command"
        commands.append(span[len(_PREFIX) + 1 :].split())
    return commands


# The forms the skill quotes, and the matching-only forms it does not quote yet (RULINGS "The
# five pinned-form tests": 07.2-02 added ("giveup",), 07.2-03 ("plan",); 07.2-09 teaches them and
# empties it, D-26).
SKILL_FORMS = hooks.MATCHING_FORMS
PENDING_SKILL_FORMS = ()


def test_skill_commands_are_the_wrapper_forms():
    commands = _commands(_text())
    for argv in commands:
        literal = tuple(argv) in hooks.MATCHING_FORMS  # `asm <NAME>` is quoted literally (F27)
        assert literal or hooks.attempt_form_matches(argv, hooks.MATCHING_FORMS), argv
    quoted = {tuple(argv) for argv in commands}
    assert quoted == set(SKILL_FORMS), "every quoted form is a skill form, and each is quoted"
    assert set(SKILL_FORMS) | set(PENDING_SKILL_FORMS) == set(hooks.MATCHING_FORMS)
    assert not set(SKILL_FORMS) & set(PENDING_SKILL_FORMS)


def test_skill_settles_the_baseline_facts():
    """What the RED baseline agents had to guess, each stated once (writing-skills RED)."""
    text = _text()
    assert "600000" in text  # ruling F33: the sweep runs with the Bash tool's longest timeout
    assert "run_in_background" in text  # security finding 1: one check at a time
    assert "checks/NNNN.json" in text and "checks/NNNN.c" in text  # where the evidence is
    assert "notes.md" in text
    for code in ("0", "1", "2"):
        assert f"`{code}`" in text  # check's exit codes


# ---- fix round 1 M5: anchors, short attempt forms, JSON field names ----

_HEADING = re.compile(r"(?m)^#{2,3} (.+)$")
_JSON_PATH = re.compile(r"[a-z_]+(\[\])?(\.[a-z_]+(\[\])?)+")  # a dotted path: reloc.ok
_JSON_KEY = re.compile(r"[a-z_]+(\[\])?")  # a bare key: ok, splice[]
_FILE_SUFFIXES = (".md", ".c", ".h", ".json", ".jsonl", ".txt", ".csv", ".s", ".toml", ".py")


def _slug(heading: str) -> str:
    """GitHub's anchor for a heading: lower case, punctuation dropped, spaces to hyphens."""
    kept = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return kept.replace(" ", "-")


def anchors_problems(text: str) -> list[str]:
    """Every `path#anchor` span whose anchor is no `## `/`### ` heading of the linked file."""
    problems = []
    for span in _spans(text):
        path = _repo_path(span)
        if path is None or "#" not in span:
            continue
        anchor = span.split("#", 1)[1].rstrip(".,;)")
        target = REPO_ROOT / path
        slugs = {_slug(h) for h in _HEADING.findall(target.read_text(encoding="utf-8"))}
        if anchor not in slugs:
            problems.append(span)
    return problems


def test_skill_anchors_resolve():
    text = _text()
    assert any("#" in span for span in _spans(text) if _repo_path(span))
    assert anchors_problems(text) == []


def attempt_form_problems(text: str) -> list[str]:
    """Every backticked span naming `attempt <sub>` (short or full form) whose argv after
    `attempt` is not one of a matching session's wrapper forms (07.2-09: MATCHING_FORMS)."""
    forms = hooks.MATCHING_FORMS
    problems = []
    for span in _spans(text):
        tokens = span.split()
        if "attempt" not in tokens:
            continue
        argv = tokens[tokens.index("attempt") + 1 :]
        if tuple(argv) not in forms and not hooks.attempt_form_matches(argv, forms):
            problems.append(span)
    return problems


def test_skill_short_attempt_forms_are_wrapper_forms():
    text = _text()
    assert any(span.startswith("attempt ") for span in _spans(text))  # the short forms
    assert attempt_form_problems(text) == []


def _key_paths(doc: object, prefix: str = "") -> set[str]:
    """Every key path of a JSON document: `functions[]`, `functions[].reloc.ok`, ..."""
    paths: set[str] = set()
    if isinstance(doc, dict):
        for key, value in doc.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, list):
                paths.add(path)  # quoted with or without the brackets
                path += "[]"
                paths.add(path)
                for item in value:
                    paths |= _key_paths(item, path)
            else:
                paths.add(path)
                paths |= _key_paths(value, path)
    return paths


def _made_up_json_keys() -> set[str]:
    """Key paths of check's to_json for a made-up verdict and sweep, plus checks.jsonl's
    line keys (the wrapper's own log), each also as every suffix after a `.` boundary."""
    from reverseapoc import attempt, check
    from reverseapoc.functions import FunctionRow
    from reverseapoc.land import LandResult
    from reverseapoc.relocs import RelocResult

    reloc = RelocResult(False, ("0x00010004: made-up problem",), frozenset(), frozenset())
    first = check.WindowRow(True, check.WindowInsn(0x10004, "inc", "ecx", False),
                            check.WindowInsn(0x10004, "inc", "edx", False))  # fmt: skip
    fn = check.FunctionCheck("func_00010000", 0x10000, 16, 87.5, reloc, False, 3, 0x10004,
                             window=(first,))  # fmt: skip
    land = check.ExeLand("UFO2P.EXE", LandResult(b"", "0" * 40, "1" * 40, (), 0, 0x10004))
    row = FunctionRow(0x10010, 0x10020, "func_00010010", "game", "u_00010000", "call")
    result = check.CheckResult(
        "ufo2p", "u_00010000", "wcc386@10.6", ("-4r",), (fn,), (land,),
        problems=(check.Unaccounted("func_00010020", 0x10020, "made-up reason"),), stubs=(row,),
    )  # fmt: skip
    cell = check.SweepCell(1, "10.6", ("-4r", "-s", "-fpi"), "", 87.5, True, 3)
    sweep = check.SweepReport("ufo2p", "u_00010000", "func_00010000", False, (cell,), (cell,),
                              Path("sweep.log"))  # fmt: skip
    staged = _stage2_sweep().to_json()  # 07-35: a sweep whose D-15 second stage ran
    line = attempt.CheckLogLine(1, 1, False, 87.5, False, False, False, None, "checks/0001.c")
    paths = (_key_paths(result.to_json()) | _key_paths(sweep.to_json()) | _key_paths(staged)
             | set(line.to_json()))  # fmt: skip
    return {path.split(".", i)[-1] for path in paths for i in range(path.count(".") + 1)}


def _json_block(text: str) -> str:
    """From the line that starts `check's JSON` to the next `### ` heading."""
    start = text.index("\ncheck's JSON")
    return text[start : text.index("\n### ", start)]


def json_field_problems(text: str) -> list[str]:
    """Every dotted JSON path anywhere in the skill, and every bare key in its JSON block, that
    check's to_json (or checks.jsonl) does not have."""
    keys = _made_up_json_keys()
    dotted = [s for s in _spans(text) if _JSON_PATH.fullmatch(s) and not s.endswith(_FILE_SUFFIXES)]
    bare = [s for s in _spans(_json_block(text)) if _JSON_KEY.fullmatch(s)]
    return [span for span in [*dotted, *bare] if span not in keys]


def test_skill_json_fields_exist():
    text = _text()
    assert "bytes.first_va" in text and "objdiff_percent" in text
    assert json_field_problems(text) == []


# ---- fix round 1: what the skill states ----


def _section(text: str, title: str) -> str:
    start = text.index(f"\n## {title}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def test_skill_states_the_exit_codes_in_the_wrapper_section():
    """M10, I1(c), I1(d): the exit codes live in D-19's section 8; 0 is the claimed function's
    match; a sweep's exit rule is stated and is never a match."""
    text = _text()
    wrapper = _section(text, "The attempt wrapper")
    for code in ("`0`", "`1`", "`2`"):
        assert code in wrapper
    assert "not compiled" in wrapper and "claimed function" in wrapper
    assert "`0` matched" not in text
    assert "never a match" in wrapper and "exits `0` when it ran" in wrapper


def test_skill_states_what_a_sweep_cell_reports():
    """R1: a sweep cell reports objdiff, reloc_ok and differing; a hit is never a match until
    a plain check under the new rule passes."""
    wrapper = _section(_text(), "The attempt wrapper")
    for field in ("`objdiff_percent`", "`reloc_ok`", "`differing`"):
        assert field in wrapper
    assert "a sweep hit is never a match" in wrapper.lower()


def test_skill_states_the_timing_rules():
    """M1, M2: the 600000 ms Bash timeout on every check; no unmeasured per-check figure, the
    budget is the elapsed time the wrapper prints."""
    text = _text()
    assert "600000" in text and "every `attempt check`" in text
    assert "90 s" not in text and "15 checks" not in text
    assert "elapsed" in text


def test_skill_states_the_lint_and_file_order_rules():
    """M3, M4 (and R2)."""
    text = _text()
    assert "the driver lints the unit before it commits a match" in text
    assert "file order does not change check's verdict" in text.lower()
    assert "jump-table function" in text and "docs/matching.md" in text


def test_pragma_policy_is_every_pragma():
    """M14: no `#pragma` of any kind during the pilot, in the skill, the src rules and the
    coding style (D-18 is the superset)."""
    for path in (SKILL, REPO_ROOT / ".claude" / "rules" / "src.md",
                 REPO_ROOT / "docs" / "coding-style.md"):  # fmt: skip
        text = path.read_text(encoding="utf-8")
        assert "no `#pragma` of any kind" in text, path
        assert "human-reviewed" in text, path


# ---- 07-35: view mode (D-15, D-19, D-24) ----

_STAGE1_SPEC = "wcc386@10.6 -4r -s -fpi"  # the `*` default, the stage-1 cell the sample keeps
_SRC_UNIT = "src/<exe>/<unit>.c"


def _stage2_sweep():
    """A made-up sweep shaped like the skill's sample: no perfect stage-1 cell, the best at 98.9%
    with its relocation check passing, so stage 2 ran (from cell 31) and its cell 42 hit."""
    from reverseapoc import check

    best = check.SweepCell(1, "10.6", ("-4r", "-s", "-fpi"), "", 98.9, True, 6, 0x0008AB14, 180)
    hit = check.SweepCell(42, "10.6", ("-4r", "-s", "-fpi", "-zp4"), "", 100.0, True, 0, None, 180)
    return check.SweepReport("ufo2p", "u_00089980", "func_0008AAF0", False, (best,), (best,),
                             Path("sweep.log"), (hit,), (hit,))  # fmt: skip


def test_skill_names_the_view_unit():
    """07-35: the session's only C file is its private view unit, named by the driver's
    REVERSEAPOC_UNIT_FILE (and in its /goal), in the description, the quick reference and the
    two sections that send the agent to the file."""
    text = _text()
    assert "REVERSEAPOC_UNIT_FILE" in text
    assert "view unit" in _frontmatter(text)["description"]
    for title in ("Replacing INCLUDE_ASM", "The attempt wrapper"):
        assert "REVERSEAPOC_UNIT_FILE" in _section(text, title), title
    assert "build/driver/<run>/<exe>/<func>/attempt-<n>/view/src/<exe>/<unit>.c" in text


def test_skill_does_not_send_agents_to_src():
    """07-35 (07-13 as built): no instruction to edit src/<exe>/<unit>.c or to add a header.
    A line may name the repo-root unit only to say the session never writes it."""
    text = _text()
    assert "src/" not in _frontmatter(text)["description"]
    outside_view = text.replace("view/" + _SRC_UNIT, "view unit")  # the view path is the file
    lines = [line for line in outside_view.splitlines() if _SRC_UNIT in line]
    assert lines, "the skill says the repo-root unit is not the session's file"
    for line in lines:
        assert "never" in line.lower(), line
    assert "a new header" not in text
    assert "no header" in text.lower()
    assert "view/include/" in text and "view/config/" in text  # the copies the Never list names


def test_skill_states_the_view_flags_rule():
    """RED-FINDINGS teach 2: the check's rule is the unit's rule in the view's config/cflags.txt
    (HEAD's copy); a sweep hit goes to the executor's `flags propose`, the owner approves."""
    flags = _section(_text(), "Flags")
    assert "view's `config/cflags.txt`" in flags
    assert "flags propose" in flags and "flags approve" in flags
    assert "checks/NNNN.c" in flags


def test_skill_states_the_second_sweep_stage():
    """D-15 (07-14 as built): stage 2 runs after a near miss (no perfect cell, the best at or above
    check.SWEEP2_FLOOR with reloc ok), under 10.6, numbered on from the stage-1 cells, and its
    hit comes through the same sweep hit line."""
    from reverseapoc import check

    wrapper = _section(_text(), "The attempt wrapper")
    assert "stage 2" in wrapper and "`stage2`" in wrapper
    assert f"{check.SWEEP2_FLOOR:g}%" in wrapper
    widest = check.SweepCell(1, "10.6", ("-4r", "-ox", "-s", "-fpi"))  # a cell with an -o set
    assert f"up to {len(check.sweep2_cells(widest))} cells" in wrapper
    assert "31 or 61" in wrapper


def test_skill_quotes_the_real_sweep_output():
    """RED-FINDINGS teach 5: the sample's body lines are exactly what attempt check --sweep
    prints for the same cells (attempt._sweep_summary), so the agent reads the stage."""
    from reverseapoc import attempt

    doc = _stage2_sweep().to_json()
    line = attempt._sweep_line(doc, _STAGE1_SPEC, attempt.Ran(0, "", ""), 16, "checks/0016.c")
    assert line.sweep_hit == "wcc386@10.6 -4r -s -fpi -zp4"
    wrapper = _section(_text(), "The attempt wrapper")
    for printed in attempt._sweep_summary(doc, line):
        assert printed in wrapper, printed


def test_skill_describes_the_difference_window():
    """261109-gzv: check's summary prints our instructions beside the original's at the first
    difference (functions[].window), and each sweep cell reports first_va and size; the skill
    says so and no longer tells the session it has no view of its own object."""
    text = _text()
    wrapper = _section(text, "The attempt wrapper")
    for name in ("`window[]`", "`(relocated)`", "`first_va`", "`size`"):
        assert name in wrapper, name
    assert "no disassembly of your own object" not in text


def test_skill_keeps_names_placeholders():
    """RED-FINDINGS teach 3: a matching session renames nothing; a name idea goes in notes.md
    and naming is the readability pass (D-19), as the watcom-readability skill says."""
    text = _text()
    assert "readability" in text and "D-19" in text
    assert "rename" in _section(text, "Replacing INCLUDE_ASM")


def test_skill_says_proposals_are_allowed_but_not_applied():
    """Fix round 1 I1: the hooks allow proposals.jsonl in every session (REVERSEAPOC_PROPOSALS,
    and the include/ denial points at it), but nothing applies a matching session's proposals:
    the rename step (07-34) runs for readability sessions only. The skill says so where
    it lists the writes, and docs/workflow.md where it lists the variable."""
    text = _text()
    writes = next(line for line in text.splitlines() if line.startswith("| What you may write"))
    assert "REVERSEAPOC_PROPOSALS" in writes and "proposals.jsonl" in writes
    assert "writes none" in writes and "readability sessions only" in writes
    assert "denial" in writes
    assert "proposals.jsonl" in hooks._view_denial(["include/x.h"])  # the hint the line answers
    workflow = (REPO_ROOT / "docs" / "workflow.md").read_text(encoding="utf-8")
    env = next(line for line in workflow.splitlines()
               if line.startswith("- `REVERSEAPOC_PROPOSALS`"))  # fmt: skip
    # 07-38: the rename step is built (07-34), so the docs say it runs after readability
    # sessions only instead of calling it planned.
    assert "matching" in env and "nothing reads" in env and "readability sessions only" in env


def test_skill_states_the_naming_landing_as_built():
    """Fix round 1 M1, refreshed by 07-38 fix round 1 (review M8): the driver step that applies
    readability proposals (renames and shared headers) is built (07-34, 07-38), so the skill no
    longer calls it planned; both mentions still say naming is the readability pass's work."""
    text = _text()
    assert "planned" not in text and "not built" not in text
    section = _section(text, "Replacing INCLUDE_ASM")
    for phrase in ("through its proposals", "through readability proposals"):
        assert phrase in section, phrase


# ---- 261109-gzx: the stop rules are the /goal's ----


def _stop_bullets(section: str) -> list[str]:
    """The bullets (without `- `) right after the section's first line that starts `Stop `."""
    lines = section.splitlines()
    lead = next(i for i, line in enumerate(lines) if line.startswith("Stop "))
    bullets = []
    for line in lines[lead + 1 :]:
        if not line.startswith("- "):
            break
        bullets.append(line[2:])
    return bullets


def test_skill_stop_rules_are_the_goal_stop_rules():
    """261109-gzx: "When to give up" lists exit 0 and then session.STOP_RULES, in the /goal's
    order and words, so the /goal's Stop hook admits every stop the skill asks for."""
    section = _section(_text(), "When to give up")
    bullets = _stop_bullets(section)
    assert len(bullets) == 1 + len(session.STOP_RULES), bullets
    assert "Stop only when one of these holds" in section
    assert bullets[0].startswith("`attempt check` exited `0`")
    for bullet, rule in zip(bullets[1:], session.STOP_RULES, strict=True):
        assert bullet.startswith(rule), (bullet, rule)


def test_skill_stops_after_a_sweep_hit():
    """261109-gzx: after a sweep hit the session writes it in notes.md and stops, because the
    driver parks the function (261109-gzu); a stop names its rule in the last message, and a
    blocked stop with no rule holding goes back to the next C shape."""
    text = _text()
    section = _section(text, "When to give up")
    assert "no new session on the function for the rest of the night" in section
    assert "last message" in section
    assert "next C shape" in section
    assert "write it in notes.md and stop" in _section(text, "Flags")
    assert "or try C shapes under the unit's rule within the budget" not in text  # today's L195
    assert "editing on loses nothing" not in text  # today's L60


# ---- 07.2-09: plan, notes, give-up and the region board (999.5-999.7, D-01..D-05) ----


def _quoted(section: str) -> set[str]:
    return set(_spans(section))


def test_skill_teaches_the_session_files():
    """D-01..D-04: the skill names plan.json and check-note.json (with `attempt plan`) where it
    teaches the wrapper, and giveup.json (with `attempt giveup`) where it teaches stopping, each
    with the exact fields the validators take; the tool writes `observed`, never the session."""
    from reverseapoc import attempt

    text = _text()
    wrapper = _quoted(_section(text, "The attempt wrapper"))
    stop = _quoted(_section(text, "When to give up"))
    for name in (hooks.PLAN_NAME, hooks.CHECK_NOTE_NAME, "attempt plan", "checks/NNNN.note.json",
                 *attempt.PLAN_KEYS, *attempt.REGION_KEYS, *attempt.NOTE_KEYS, attempt.OBSERVED):
        assert name in wrapper, name
    for name in (hooks.GIVEUP_NAME, "attempt giveup", *attempt.GIVEUP_KEYS):
        assert name in stop, name


def test_skill_names_every_giveup_category():
    """D-04: the `category` line of "When to give up" lists exactly attempt.GIVEUP_CATEGORIES,
    in order, so a later change to the categories breaks this test, not a night (T-07.2-25)."""
    from reverseapoc import attempt

    section = _section(_text(), "When to give up")
    line = next((line for line in section.splitlines() if line.startswith("- `category`")), "")
    assert tuple(_SPAN.findall(line)[1:]) == attempt.GIVEUP_CATEGORIES, line
    assert "no C" in section  # T-07.2-26: the texts are prose, never code


def test_skill_names_the_region_board():
    """999.7 (07.2-05): at BOARD_MIN_SIZE and up the check summary prints the region board; the
    skill says when, what `exact in` means, and names the pack's earlier give-ups and best C."""
    from reverseapoc import attempt, contextpack

    wrapper = _section(_text(), "The attempt wrapper")
    assert "region board" in wrapper
    assert f"{attempt.BOARD_MIN_SIZE} B" in wrapper
    assert "exact in" in wrapper and "closest" in wrapper
    for title in (contextpack.TITLE_GIVEUPS, contextpack.TITLE_BEST_C):
        assert f'"{title}"' in wrapper, title


def test_skill_says_a_refused_check_costs_nothing():
    """D-01: a check without a plan or a note is refused with exit 2 and uses none of the 25
    runs; the quick reference's budget row and the wrapper section both say so."""
    text = _text()
    budget = next(line for line in text.splitlines() if line.startswith("| Check budget"))
    assert hooks.PLAN_NAME in budget and hooks.CHECK_NOTE_NAME in budget, budget
    assert "counts nothing" in budget
    wrapper = _section(text, "The attempt wrapper")
    assert f"none of the {session.MAX_CHECK_RUNS}" in wrapper
    assert "write plan.json beside notes.md first" in wrapper  # the refusal as it prints

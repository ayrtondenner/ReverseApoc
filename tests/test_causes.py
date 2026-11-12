"""`reverseapoc causes` (999.8, plan 07.2-04): failed builds and mismatches counted by cause
over drive run directories, from saved evidence only.

Every test builds a synthetic build/driver/<run>/<exe>/<function>/attempt-N under tmp_path:
checks.jsonl lines and checks/NNNN.json documents written here, no game bytes, never the real
runs."""

from __future__ import annotations

import json
import re
from pathlib import Path

from reverseapoc import causes, cli
from reverseapoc.functions import FunctionRow, format_functions_csv

_FUNCTION = "func_00012340"


# ---- synthetic run directories ----


def _attempt(repo: Path, run: str, function: str = _FUNCTION, exe: str = "ufo2p",
             n: int = 1) -> Path:  # fmt: skip
    attempt_dir = repo / "build" / "driver" / run / exe / function / f"attempt-{n}"
    attempt_dir.mkdir(parents=True)
    return attempt_dir


def _line(n: int, exit_code: int, *, sweep: bool = False, **extra) -> dict:
    """A checks.jsonl line with the plain-check keys of RESEARCH Q5."""
    return {"best_percent": 100.0 if exit_code == 0 else 50.0, "bytes_ok": exit_code == 0,
            "exit": exit_code, "n": n, "readlint_violations": 0, "readlint_waivers": 0,
            "reloc_ok": exit_code != 2, "source": f"checks/{n:04d}.c", "splice_ok": True,
            "sweep": sweep, "sweep_hit": False, **extra}  # fmt: skip


def _log(attempt_dir: Path, lines: list) -> None:
    text = "".join((ln if isinstance(ln, str) else json.dumps(ln)) + "\n" for ln in lines)
    (attempt_dir / "checks.jsonl").write_text(text, encoding="utf-8")


def _five(attempt_dir: Path) -> None:
    """3 plain exit 1, 1 plain exit 0, 1 plain exit 2 and 2 sweeps."""
    plain = [_line(n, e) for n, e in enumerate((1, 1, 1, 0, 2), start=1)]
    _log(attempt_dir, [*plain, _line(6, 1, sweep=True), _line(7, 0, sweep=True)])


def _json(capsys, *argv: str) -> dict:
    assert cli.main(["causes", "--json", *argv]) == 0
    return json.loads(capsys.readouterr().out)


# ---- per-try rates (Task 1) ----


def test_rates(tmp_path):
    _five(_attempt(tmp_path, "run-a"))
    (row,) = causes.collect(tmp_path, ["run-a"]).to_json()["runs"]
    assert row["run"] == "run-a" and row["checks"] == 5
    assert (row["build_failure"], row["build_failure_percent"]) == (1, "20.0")
    assert (row["mismatch"], row["mismatch_percent"]) == (3, "60.0")
    assert (row["match"], row["match_percent"]) == (1, "20.0")
    assert row["sweeps"] == 2


def test_two_runs_and_total(tmp_path):
    _five(_attempt(tmp_path, "run-a"))
    _five(_attempt(tmp_path, "run-b", function="func_00012350"))
    _log(_attempt(tmp_path, "run-b", n=2), [_line(1, 0)])
    report = causes.collect(tmp_path, ["run-a", "run-b"])
    doc = report.to_json()
    assert [r["run"] for r in doc["runs"]] == ["run-a", "run-b"]
    assert [r["checks"] for r in doc["runs"]] == [5, 6]
    total = doc["rates"]
    counts = (total["checks"], total["match"], total["mismatch"], total["build_failure"])
    assert counts == (11, 3, 6, 2)
    assert total["match_percent"] == "27.3" and doc["sweeps"] == 4
    text = report.format()
    assert "run-a" in text and "run-b" in text and "total" in text and "27.3%" in text


def test_unknown_run_is_exit_2(tmp_path, capsys):
    _five(_attempt(tmp_path, "run-a"))
    assert cli.main(["causes", "nosuch", "--repo", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("reverseapoc causes: error:") and "nosuch" in captured.err
    assert "Traceback" not in captured.err


def test_no_run_named_reads_every_run(tmp_path, capsys):
    _five(_attempt(tmp_path, "run-a"))
    _five(_attempt(tmp_path, "run-b"))
    doc = _json(capsys, "--repo", str(tmp_path))
    assert [r["run"] for r in doc["runs"]] == ["run-a", "run-b"]
    assert doc["rates"]["checks"] == 10


def test_ignores_extra_keys(tmp_path):
    attempt_dir = _attempt(tmp_path, "run-a")
    noted = _line(2, 0, note="checks/0002.note.json")  # 07.2-03's key
    _log(attempt_dir, [_line(1, 1), noted, "{not json", "[1, 2]", _line(3, 7)])
    doc = causes.collect(tmp_path, []).to_json()
    assert (doc["rates"]["checks"], doc["rates"]["match"], doc["rates"]["mismatch"]) == (2, 1, 1)
    assert doc["malformed"] == 3 and doc["runs"][0]["malformed"] == 3


def test_an_empty_checkout_prints_a_zero_total(tmp_path, capsys):
    assert cli.main(["causes", "--repo", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "total" in out and "0 checks" in out


def test_help_names_run_and_says_it_never_compiles(capsys):
    try:
        cli.main(["causes", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "RUN" in out and "--json" in out and "--repo" in out and "never compiles" in out


# ---- Watcom codes, mismatch classes, shared-header gaps (Task 2) ----

_START = 0x12340
_ROW_SIZE = 0x20


def _doc(attempt_dir: Path, n: int, doc: dict) -> None:
    checks = attempt_dir / "checks"
    checks.mkdir(exist_ok=True)
    (checks / f"{n:04d}.json").write_text(json.dumps(doc), encoding="utf-8")


def _tool_error(stdout: str = "", stderr: str = "") -> dict:
    """attempt.py's saved document when check printed no usable JSON."""
    return {"error": "no usable JSON", "returncode": 2, "stdout": stdout, "stderr": stderr}


def _failed(attempt_dir: Path, *outputs: str) -> None:
    """One plain exit-2 check per output, each with its tool-error document."""
    _log(attempt_dir, [_line(n, 2) for n in range(1, len(outputs) + 1)])
    for n, text in enumerate(outputs, start=1):
        _doc(attempt_dir, n, _tool_error(stderr="reverseapoc check: error: compile failed: "
                                                "FAILED  v.c  -4r  exit 1\n" + text))  # fmt: skip


def _entry(*, size: int = _ROW_SIZE, reloc_problems: tuple[str, ...] = (), bytes_ok: bool = False,
           window: tuple[dict, ...] = ()) -> dict:  # fmt: skip
    """check's JSON for the claimed function (check.FunctionCheck.to_json)."""
    return {"name": _FUNCTION, "va": f"0x{_START:08X}", "size": size, "objdiff_percent": 90.0,
            "reloc": {"ok": not reloc_problems, "problems": list(reloc_problems)},
            "bytes": {"ok": bytes_ok, "differing": 0 if bytes_ok else 3,
                      "first_va": None if bytes_ok else f"0x{_START + 4:08X}", "filler": 0,
                      "regions": []},
            "raw_fields": [], "window": list(window)}  # fmt: skip


def _check_doc(functions: list, problems: tuple[dict, ...] = ()) -> dict:
    return {"exe": "ufo2p", "unit": "u_00010000", "compiler": "10.6", "flags": ["-4r"],
            "functions": functions, "problems": list(problems), "stubs": [], "splice": [],
            "target": {"raw_fields": [], "undecoded": []}, "ok": False}  # fmt: skip


def _insn(mnemonic: str, operands: str = "eax, 1") -> dict:
    return {"va": f"0x{_START + 4:08X}", "mnemonic": mnemonic, "operands": operands,
            "relocated": False}  # fmt: skip


_WINDOW = ({"first": False, "ours": _insn("push"), "original": _insn("push")},
           {"first": True, "ours": _insn("mov"), "original": _insn("lea")})  # fmt: skip


def _config(repo: Path) -> Path:
    config = repo / "config"
    (config / "ufo2p").mkdir(parents=True)
    rows = [FunctionRow(_START, _START + _ROW_SIZE, _FUNCTION, "game", "u_00010000", "call")]
    (config / "ufo2p" / "functions.csv").write_text(format_functions_csv(rows, "UFO2P.EXE"),
                                                   encoding="utf-8")  # fmt: skip
    return config


def test_codes(tmp_path):
    _failed(_attempt(tmp_path, "run-a"),
            "v.c(3): Error! E1009: Expecting ';' but found 'x'\n",
            "v.c(4): Error! E1011: Symbol 'foo' has not been declared\n"
            "v.c(9): Error! E1011: Symbol 'bar' has not been declared\n",
            "v.c(1): Warning! W101: Non-portable pointer conversion\n" * 3)  # fmt: skip
    doc = causes.collect(tmp_path, []).to_json()
    assert doc["codes"] == {"E1009": 1, "E1011": 2, "W101": 3}
    assert doc["build_failures"] == {
        "compile failed: v.c(3): Error! E1009: Expecting ';' but found 'x'": 1,
        "compile failed: v.c(4): Error! E1011: Symbol 'foo' has not been declared": 1,
        "compile failed: reverseapoc check: error: compile failed: FAILED  v.c  -4r  exit 1": 1,
    }


def test_an_exit_2_check_doc_is_keyed_by_its_first_problem(tmp_path):
    attempt_dir = _attempt(tmp_path, "run-a")
    _log(attempt_dir, [_line(1, 2), _line(2, 2)])
    problem = {"name": "func_00012350", "va": None, "reason": "a stray public"}
    _doc(attempt_dir, 1, _check_doc([], (problem,)))  # checks/0002.json is missing
    doc = causes.collect(tmp_path, []).to_json()
    assert doc["build_failures"] == {"check: a stray public": 1, "no saved check document": 1}
    assert doc["codes"] == {} and doc["header_gaps"] == []


def test_mismatch_classes(tmp_path):
    config = _config(tmp_path)
    attempt_dir = _attempt(tmp_path, "run-a")
    not_a_function = {"name": _FUNCTION, "va": f"0x{_START:08X}",
                      "reason": "is defined in C but is not a function of the unit"}  # fmt: skip
    docs = [
        _check_doc([_entry(reloc_problems=("0x00012345: call target 0x10 differs",),
                           bytes_ok=True)]),  # fmt: skip
        _check_doc([_entry(size=_ROW_SIZE - 2)]),
        _check_doc([_entry(window=_WINDOW)]),
        _check_doc([_entry()]),
        _check_doc([], (not_a_function,)),
        _check_doc([{**_entry(), "name": "func_00012350"}]),  # the claimed one is absent
        {"functions": "not a list"},
    ]
    _log(attempt_dir, [_line(n, 1) for n in range(1, len(docs) + 2)])  # the last has no doc
    for n, doc in enumerate(docs, start=1):
        _doc(attempt_dir, n, doc)
    got = causes.collect(tmp_path, [], config=config).to_json()["mismatch_classes"]
    assert got == {"reloc: call target N differs": 1, "length": 1, "bytes: mov/lea": 1,
                   "bytes": 1, "not compiled": 2, "unreadable check document": 1,
                   "no saved check document": 1}  # fmt: skip


def test_mismatch_classes_read_config_under_the_repo_by_default(tmp_path):
    _config(tmp_path)
    attempt_dir = _attempt(tmp_path, "run-a")
    _log(attempt_dir, [_line(1, 1)])
    _doc(attempt_dir, 1, _check_doc([_entry(size=_ROW_SIZE + 1)]))
    assert causes.collect(tmp_path, []).to_json()["mismatch_classes"] == {"length": 1}


# ---- hex address fold (todo causes-hex-address-keys) ----

_TAIL = ("0x000ABCE0: length differs: ours 16 bytes, original 32 bytes; the original's tail is "
         "not alignment filler")  # fmt: skip
_TAIL_KEY = ("reloc: length differs: ours N bytes, original N bytes; the original's tail is not "
             "alignment filler")  # fmt: skip


def _reloc_mismatches(repo: Path, problems: tuple[str, ...]) -> None:
    """One plain exit-1 check per problem, each the claimed entry's first reloc problem."""
    attempt_dir = _attempt(repo, "run-a")
    _log(attempt_dir, [_line(n, 1) for n in range(1, len(problems) + 1)])
    for n, problem in enumerate(problems, start=1):
        _doc(attempt_dir, n, _check_doc([_entry(reloc_problems=(problem,))]))


def test_a_hex_address_folds_to_one_placeholder(tmp_path, capsys):
    _config(tmp_path)
    # Made-up addresses, in relocs._va's uppercase 0x%08X form.
    _reloc_mismatches(tmp_path, (
        f"{_TAIL} (pop at 0x000ABCDE)",
        f"{_TAIL} (pop at 0x00041234)",
        f"{_TAIL} (pop at 0x000B1F3C)",
        f"{_TAIL} (ret at 0x000ABCDE)",
        "0x00012350: _TEXT+0x1a3 (func_00023D50_) resolves to 0x000D65AB, the original "
        "targets 0x000D67CD",
    ))  # fmt: skip
    got = _json(capsys, "--repo", str(tmp_path))["mismatch_classes"]
    resolves = "reloc: _TEXT+N (func_00023D50_) resolves to N, the original targets N"
    assert got == {f"{_TAIL_KEY} (pop at N)": 3, f"{_TAIL_KEY} (ret at N)": 1, resolves: 1}


def test_a_bare_hex_run_after_at_folds_to_one_placeholder(tmp_path):
    config = _config(tmp_path)
    # Made-up addresses: one bare hex run after "at", one in the 0x form.
    _reloc_mismatches(tmp_path, (
        "0x00012345: the original's tail is not alignment filler (add at 4A10C2)",
        "0x00012345: the original's tail is not alignment filler (add at 0x0004A10C)",
    ))  # fmt: skip
    got = causes.collect(tmp_path, [], config=config).to_json()["mismatch_classes"]
    assert got == {"reloc: the original's tail is not alignment filler (add at N)": 2}


def test_the_hex_fold_keeps_words_and_identifiers(tmp_path):
    config = _config(tmp_path)
    attempt_dir = _attempt(tmp_path, "run-a")
    # Made-up addresses; an identifier keeps its digits, a word after "at" stays.
    entries = [
        _entry(reloc_problems=("0x00012345: _D_000126F0: 0x000126F0 is in no data object and "
                               "starts no data-in-code row",)),  # fmt: skip
        _entry(reloc_problems=("0x00012345: a target at face value",)),
        _entry(reloc_problems=("0x00012345: the fixup at a field edge",)),
        {**_entry(), "reloc": {"ok": False, "problems": []}},
    ]
    _log(attempt_dir, [_line(n, 1) for n in range(1, len(entries) + 1)])
    for n, entry in enumerate(entries, start=1):
        _doc(attempt_dir, n, _check_doc([entry]))
    got = causes.collect(tmp_path, [], config=config).to_json()["mismatch_classes"]
    assert got == {"reloc: _D_000126F0: N is in no data object and starts no data-in-code row": 1,
                   "reloc: a target at face value": 1, "reloc: the fixup at a field edge": 1,
                   "reloc": 1}  # fmt: skip


def test_header_gaps_ranked(tmp_path):
    foo = "v.c(4): Error! E1011: Symbol 'foo' has not been declared\n"
    bar = "v.c(5): Error! E1011: Symbol 'bar' has not been declared\n"
    _failed(_attempt(tmp_path, "run-a", function="func_00012340"), foo, foo)  # one function
    _failed(_attempt(tmp_path, "run-a", function="func_00012350"), foo + bar)
    _failed(_attempt(tmp_path, "run-b", function="func_00012360"),
            "v.c(7): Error! E1045: Subscript on non-array 'struct unk_0010'\n")  # fmt: skip
    _failed(_attempt(tmp_path, "run-b", function="func_00012370"),
            "v.c(8): Error! E1045: Subscript on non-array\n")  # no quoted name: the message
    report = causes.collect(tmp_path, [])
    assert report.to_json()["header_gaps"] == [
        {"name": "foo", "functions": 2},
        {"name": "Subscript on non-array", "functions": 1},
        {"name": "bar", "functions": 1},
        {"name": "struct unk_0010", "functions": 1},
    ]
    gaps = report.format().split("shared-header gaps")[1]
    assert "none" not in gaps and gaps.index("foo") < gaps.index("struct unk_0010")


def test_an_empty_gap_ranking_prints_none(tmp_path):
    _five(_attempt(tmp_path, "run-a"))
    report = causes.collect(tmp_path, [])
    assert report.to_json()["header_gaps"] == []
    assert "shared-header gaps: none" in report.format()


def test_few_build_failures_are_called_out(tmp_path):
    attempt_dir = _attempt(tmp_path, "run-a")
    _log(attempt_dir, [_line(1, 2), *(_line(n, 1) for n in range(2, 102))])
    assert "build failures were few" in causes.collect(tmp_path, []).format()
    _five(_attempt(tmp_path, "run-b"))
    assert "build failures were few" not in causes.collect(tmp_path, ["run-b"]).format()


def test_json_keys(tmp_path, capsys):
    _five(_attempt(tmp_path, "run-a"))
    doc = _json(capsys, "--repo", str(tmp_path))
    assert {"runs", "rates", "codes", "mismatch_classes", "header_gaps", "sweeps",
            "malformed"} <= set(doc)  # fmt: skip


def test_no_byte_value_reaches_the_report(tmp_path):
    """T-07.2-10: counts, codes, class keys and C identifiers only, never a long hex run."""
    config = _config(tmp_path)
    attempt_dir = _attempt(tmp_path, "run-a")
    hexrun = "ab" * 40
    window = ({"first": True, "ours": _insn("mov", hexrun), "original": _insn("lea", hexrun)},)
    _log(attempt_dir, [_line(1, 1), _line(2, 2)])
    _doc(attempt_dir, 1, _check_doc([_entry(window=window)]))
    _doc(attempt_dir, 2, _tool_error(stdout="v.c(2): Error! E1011: Symbol 'foo' has not been "
                                            f"declared\n{hexrun}\n", stderr=hexrun))  # fmt: skip
    doc = causes.collect(tmp_path, [], config=config).to_json()
    assert doc["mismatch_classes"] == {"bytes: mov/lea": 1}
    assert not re.search(r"[0-9A-Fa-f]{65,}", json.dumps(doc))

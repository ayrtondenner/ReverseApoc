# Phase 6: Reporting and agent pilot - Pattern Map

**Mapped:** 2026-10-24
**Files analyzed:** 38 (new + modified, incl. DI-01..DI-37 targets)
**Analogs found:** 33 / 38

Binding overrides: CONTEXT.md D-44..D-50 win over RESEARCH.md. **No `mcp.py`** (RESEARCH layout L313 is superseded); the agent reaches `check`/`asm`/`context` through a host-side attempt wrapper verb, Bash-allowlisted. All analog paths below are git-tracked (`git ls-files` verified).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `tools/reverseapoc/fileio.py` (new, DI-18) | utility | file-I/O | `tools/reverseapoc/splice.py` L685-700 `_write_atomic` | exact (move) |
| 7 importers of `_write_atomic` (asm, check, cli, compiler, functions, land, libmatch, omf2elf) + `tests/test_compiler.py:437` | modify | file-I/O | same | exact |
| `tools/reverseapoc/status.py` (new, D-20) | model | CRUD (CSV) | `tools/reverseapoc/functions.py` L123-160 (`FunctionRow`, `_format_csv`, `_write_text`, `_read_records`) | exact |
| `config/<exe>/status.csv` (new, gate-written) | config/data | CRUD | `config/<exe>/functions.csv` (comment line + header) | exact |
| `tools/reverseapoc/gate.py` (new, D-21/D-24) | service | request-response | `tools/reverseapoc/check.py` L845-895 `check_unit`; `cli.py` L898-920 | exact |
| `tools/reverseapoc/hooks.py` (new, D-15..D-17, D-44..D-46) | middleware | event-driven (stdin JSON -> stdout JSON) | `tools/reverseapoc/check.py` L351-371 `source_marks` (reuses configure `_NOT_CODE`/`_blank`); shell shape: `cli.main` | role-match |
| `tools/reverseapoc/attempt.py` + `attempt` verb (new, D-44) | controller | request-response (subprocess to container) | `cli.py` `_run_check`/`_cmd_check` L898-920; `check.CONTAINER_HINT` L88 | role-match |
| `tools/reverseapoc/contextpack.py` + `context` verb (new, D-13/D-14) | service | transform / file-I/O | `asm.py` L230-283 `select_rows`/`file_name`/`write_listings`; `ghidra.py` drafts | role-match |
| `tools/reverseapoc/driver.py` + `drive` verb (new, D-05..D-08) | service | batch / event-driven (subprocess stream) | `check.default_objdiff_runner` L518-540 (injectable runner); `cli._cmd_score` L524-540 | partial |
| `tools/reverseapoc/streamjson.py` (new) | utility | transform (pure) | `check.match_percent` L494-507 (parse foreign JSON, fail closed) | partial |
| Scorer wrapper (in driver or `score.py`, D-09/D-10) | service | transform | `cli._cmd_score` L524-540 + `score.assess` L287, `ScoreReport.build` L334 | exact |
| `tools/progress.py` (new, stdlib, runs `python -I`) | utility | batch/transform | `configure.py` (root, stdlib, standalone script, own argparse) | role-match |
| `progress/attempts.jsonl` (new) | data | append | `compiler._append_log` L490 (append-only log) | partial |
| `decomphub.progress.json` (new, root) | data | gate-written | `compiler.py` L206 json stamp via `_write_atomic` | partial |
| `config/driver/claude-settings.json` (new) | config | - | `.claude/settings.json` | role-match |
| `.claude/settings.json` (modify: `hooks` block) | config | - | itself (only `enabledPlugins` today) | exact |
| `.claude/skills/watcom-decomp/SKILL.md` (new, owner via writing-skills) | doc | - | `.claude/skills/unlazy/SKILL.md` (frontmatter shape only) | partial |
| `.github/workflows/pages.yml` (new, D-27, D-30) | config/CI | batch | `.github/workflows/ci.yml` | exact |
| `.github/workflows/ci.yml` (modify: drift test runs in pytest already) | config/CI | - | itself | exact |
| `tools/reverseapoc/cli.py` (modify: `gate`, `drive`, `attempt`, `context`, `_ERRORS`, docstring) | controller | request-response | itself L1074-1180 | exact |
| `tools/reverseapoc/asm.py` (DI-01, L245-248) | modify | file-I/O | `asm.file_name` L243-248 | exact |
| `tools/reverseapoc/check.py` (DI-02/03/04/06, cross-check) | modify | - | itself | exact |
| `tools/reverseapoc/target.py`, `relocs.py` (DI-02/03/04) | modify | transform | themselves | exact |
| `tools/reverseapoc/land.py` (DI-06 provenance stamp) | modify | file-I/O | `land.write_landed` L167-176; `compiler.py` L165-206 stamp | exact |
| `configure.py` (DI-05 backslash continuation; DI-06 `--config`) | modify | transform | itself (`_NOT_CODE`, `_live_code`) | exact |
| `tools/reverseapoc/compiler.py` (DI-11..DI-17 cc/log) | modify | file-I/O | itself L490 `_append_log`, `_reap` | exact |
| `.dockerignore` (DI-22) | config | - | itself; tested by `tests/test_hygiene.py:30` | exact |
| `.recomp.json` (DI-37) | config | - | itself | exact |
| `README.md`, `docs/*.md`, `docs/listings.md`, `docs/DECOMPHUB_VERIFICATION.md`, `.claude/rules/src.md`, `config/watcom.toml` L37/L106 | doc | - | n/a | n/a |
| `tests/test_fileio.py`, `test_status.py`, `test_gate.py`, `test_hooks.py`, `test_attempt.py`, `test_contextpack.py`, `test_driver.py`, `test_streamjson.py`, `test_progress.py`, `test_drift.py`, `test_skill.py` | test | - | `tests/test_cli.py`, `tests/test_githooks.py`, `tests/test_check_real.py`, `tests/test_hygiene.py` | exact |
| `tests/fakeclaude.py` + `tests/fixtures/stream/*.jsonl` | test fixture | streaming | `tests/watcomtree.py` `FakeCompiler` (fake tool pattern) | role-match |

## Pattern Assignments

### `tools/reverseapoc/fileio.py` (DI-18)

**Analog:** `tools/reverseapoc/splice.py` L685-700. Move verbatim, rename to `write_atomic`; keep `from .fileio import write_atomic as _write_atomic` in splice for one release (D-41).
```python
def _write_atomic(path: Path, data: bytes) -> None:
    """Write `data` to a temporary file next to `path`, then swap it in with os.replace: ..."""
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    fh = tmp.open("xb")
    try:
        with fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
```
Importers to flip: `asm.py:33`, `check.py:77`, `cli.py:83`, `compiler.py:37`, `functions.py:43`, `land.py:38`, `libmatch.py:43`, `omf2elf.py:77`. `tests/test_compiler.py:437` monkeypatches `compiler._write_atomic` - update the attribute name in the same commit.

---

### `tools/reverseapoc/status.py` (model, CSV CRUD)

**Analog:** `tools/reverseapoc/functions.py` L123-160.
```python
@dataclass(frozen=True)
class FunctionRow:
    """One functions.csv row: [start, end) in linear addresses."""
    start: int
    end: int
    ...

def _format_csv(comment: str, columns: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    buf = io.StringIO()
    buf.write(comment + "\n")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return buf.getvalue()

def _write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(path, text.encode("utf-8"))

def _read_records(path: Path, columns: Sequence[str]) -> list[dict[str, str]]:
    """The data rows of a committed CSV as dicts; comment lines (starting with #) are skipped.
    A file that is not UTF-8 or whose header is not exactly `columns` is refused."""
```
- Columns (D-20, costly to change): `start,name,unit,status,best_percent,attempts,source_sha256,date`. Addresses via `functions._address` (`_ADDRESS_FORMAT`), rows sorted by start, sparse.
- Raise a `StatusError(ValueError)` like `CheckError` (`check.py:96`) and add it to `cli._ERRORS`.
- Prefer importing `_format_csv`/`_read_records` from functions (or promote them) over copying. `tools/progress.py` cannot import them (runs `-I`, no reverseapoc) - see progress section.

---

### `tools/reverseapoc/gate.py` + `gate` verb (D-21, D-24)

**Analog:** `check.check_unit` L845-895 (signature to call) and `cli._run_check`/`_cmd_check` L898-920 (verb shell, exit 0/1/2).
```python
def check_unit(exe, unit, *, orig_dir, manifest, config_root, src_root, build_dir,
               watcom_dir=None, cflags=None, watcom_manifest=None, log=None,
               compile_fn=None, objdiff_runner=None) -> CheckResult:
```
```python
def _run_check(args):
    exe, unit = _split_unit(args.target)          # cli.py:880, "EXE/UNIT"
    result = check_unit(exe, unit, orig_dir=args.orig, manifest=args.manifest, config_root=args.config,
        src_root=args.src, build_dir=args.build, ...)
    print(json.dumps(result.to_json(), indent=2) if args.json else result.format())
    return result.exit_code

def _cmd_check(args):
    """Exit 0 matched, 1 mismatch, 2 for any tool or usage error (never a pass)."""
    try:
        return _run_check(args)
    except (*_ERRORS, CheckError) as exc:
        print(f"reverseapoc check: error: {exc}", file=sys.stderr)
        return EXIT_TOOL
```
- Reuse `EXIT_OK, EXIT_MISMATCH, EXIT_TOOL` from `check.py:83`; `_add_unit_roots(p)` (cli.py:922) for `--orig/--manifest/--config/--src/--build`.
- Cross-check (D-24): `CheckResult.splices` -> each `ExeLand` (check.py:596) carries `LandResult.landed` (row starts, land.py:161). Compare with status.csv matched set plus the unit's newly defined functions; mismatch -> `EXIT_MISMATCH`, write nothing.
- Writes status.csv and `decomphub.progress.json` with `write_atomic` only after exit 0. `gate --all` loops units with matched rows. Container-only, like check (objdiff-cli).
- Injectable `compile_fn`/`objdiff_runner` pass through, so `test_gate.py` can run without the container (pattern from `tests/test_check.py`).

---

### `tools/reverseapoc/hooks.py` (always-on + matching layers)

**Analog (text parsing):** `check.source_marks` L357-371 reuses configure's regexes rather than re-deriving them:
```python
cfg = _configure()        # check.py:330, loads root configure.py as a module
code = cfg._live_code(cfg._NOT_CODE.sub(cfg._blank, text))
```
Use the same `_configure()` loader to blank comments/literals before testing for `\b_{1,2}asm\b`, `_Pragma`, `#pragma aux` (D-16 always-on: code-emitting; D-18 matching: any). DI-05's backslash-continuation fix in configure.py must land first (wave 1) so both share it.

**Shell shape:** pure `decide(payload, *, layer, repo, env) -> Decision` + `main(argv)` like `cli.main` L1172-1178, but **fail closed**: any exception -> exit 2, reason on stderr (RESEARCH Pattern 2 step 4). Entry: `uv run --frozen python -I -m reverseapoc.hooks pre-tool-use` (add `if __name__ == "__main__": sys.exit(main())`, cli.py L1179-1180).

**Bash rule (D-44, replaces RESEARCH's MCP allow):** matching layer allows Bash only when `shlex.split(command)` equals an exact attempt-wrapper argv prefix and the raw string contains none of `; & | < > \` $( \n` (and other metachars). No `mcp__reverseapoc__*` allow.

**Notes exemption (D-46):** only `os.environ["REVERSEAPOC_ATTEMPT_NOTES"]`, resolved under `build/driver/`, name `notes.md`. Claim from `REVERSEAPOC_CLAIM=<exe>/<unit>` (parse with `cli._split_unit` rules).

**Path normalisation:** RESEARCH Pattern 2 step 1 (PureWindowsPath vs PurePosixPath, normpath, casefold, repo root by nearest `.git`).

---

### `tools/reverseapoc/attempt.py` + `attempt check|asm|context` verb (D-44)

**Analog:** `cli._add_check_command` L931-951 for argparse; `check.CONTAINER_HINT` L88 for the container command:
```python
CONTAINER_HINT = "docker compose run --rm build uv run reverseapoc check {target}"
```
- Target taken from env (`REVERSEAPOC_CLAIM`, function from `REVERSEAPOC_FUNC`), never from argv; the only agent-controlled option is `--sweep` (check) / nothing else. Refuse unknown args with exit 2 (argparse `exit_on_error`-style, mirror `_cmd_check`'s EXIT_TOOL).
- `check` -> `subprocess.run(["docker","compose","run","--rm","build","uv","run","reverseapoc","check",claim,"--json", ...])`, pass exit code through (0/1/2). `asm` -> read `asm/<exe>/<name>.s` (file name rule `asm.file_name` L243). `context` -> call contextpack.
- Use an injectable runner like `check.default_objdiff_runner` (L518-540) so tests don't need Docker.

---

### `tools/reverseapoc/contextpack.py` + `context` verb (D-13, D-14)

**Analogs:** `asm.select_rows` L230-240 (row lookup by any address), `asm.file_name` L243-248 (listing name), `asm.write_listings` L265-283 (atomic write per file), `ghidra.py` L31-38/L313-325 (draft path `asm/<exe>/ghidra/func_X.c`), `check.source_marks` (caller/callee match status from src).
```python
def write_listings(rows, *, flat, fixups, symbols, out_dir) -> AsmReport:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ...
        _write_atomic(out_dir / file_name(symbols, row), text.encode("utf-8"))
```
- Output only under gitignored `build/driver/<run>/<exe>/<func>/` (game-derived). 24 KB cap, truncate in fixed order look-alikes -> callers -> draft. Report dataclass with `format()`/`to_json()` like `AsmReport` L251-262.

---

### `tools/reverseapoc/asm.py` DI-01 (L243-248)

```python
def file_name(symbols: SymbolTable, row: FunctionRow) -> str:
    """<C name>.s, or <kind>_<start>.s for a name that is not a safe file name."""
    name = symbols.c_name(row.start)
    if not _SAFE_FILE.fullmatch(name):
        name = f"{row.kind.replace('-', '_')}_{row.start:08X}"
    return name + LISTING_SUFFIX
```
Extend the fallback condition to `name in symbols.ambiguous` (`_Alphabet` cases). Test in `tests/test_asm.py` with a synthetic SymbolTable of two same-name rows.

---

### `tools/reverseapoc/driver.py` + `drive` verb (D-05..D-08, D-48)

**Analogs:** runner injection `check.default_objdiff_runner` L518-540 (`Runner = Callable[[Sequence[str]], str]`); scorer call `cli._cmd_score` L524-540:
```python
assessments = assess(inputs.rows, flat=inputs.le.load_flat(relocate=False),
    fixups=inputs.le.fixups(), symbols=inputs.symbols,
    chk_targets=_chk_targets(inputs), runtime_starts=_runtime_starts(target))
report = ScoreReport.build(target.name, assessments, inputs.symbols, args.top)
```
- Status awareness: drop `report.candidates` whose start is in status.csv (matched/partial) or in this pass's capped set; interleave 5+5 with variety rule (<=2 per unit, <=3 per 64 KiB).
- Session launch: argv list exactly D-06 (no shell). Classification in pure `streamjson.classify(events, exit_code)`; backoff classes D-08. Flags `--max-sessions` (30), `--target-matched` (10).
- Commit message D-25; trailers set explicitly (`.githooks/commit-msg` only adds when `CLAUDECODE` set, see `tests/test_githooks.py` L1-5).
- Stray-path check: `git status --porcelain` vs allowlist (reuse hooks' path predicate, single source).
- Attempt log append: one JSON object per line to `progress/attempts.jsonl`; open-append-close like `compiler._append_log` L490.

---

### `tools/progress.py` (stdlib, `python -I`, Pages)

**Analog:** root `configure.py` - standalone stdlib script, module docstring with usage line, own `argparse`, `from __future__ import annotations`, no reverseapoc import:
```python
#!/usr/bin/env python3
"""Generate build.ninja, objdiff.json and compile_commands.json for ReverseApoc.
...
    python configure.py [--orig DIR] [--config DIR] [--src DIR] [--output build.ninja]
"""
from __future__ import annotations
import argparse
import json
...
```
- Pure `derive(status, functions, units) -> Progress`; writers for progress.json, progress.svg (treemap), progress-shield.json, report.json (objdiff `measures`/`units`/`categories` ufo2p/tacp), decomphub.progress.json. Uncovered segment per D-50.
- CSV reading: re-implement the minimal `#`-comment-skip + header check from `functions._read_records` (it cannot import it under `-I` from `tools/`). The drift test asserts its output equals gate's DecompHub file, so gate should import `progress.derive` (load by path like `check._configure` L330) rather than duplicate.

---

### `.github/workflows/pages.yml` (D-27, D-30)

**Analog:** `.github/workflows/ci.yml` (whole file):
```yaml
on:
  push:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
```
- Change: `on: push: branches: [main], paths: [...]` + `schedule` weekly; `permissions: pages: write, id-token: write, contents: read`; steps checkout@v7 -> `python -I tools/progress.py --out _site` (no uv needed) -> `actions/upload-artifact` named `X-COM_Apocalypse_DOS_report` (report.json) -> upload-pages-artifact@v5 -> deploy-pages@v5 (environment `github-pages`). DecompHub POST step gated on `vars.DECOMPHUB_REFRESH` (`if: vars... != ''`).
- ci.yml itself needs no new step: the drift test (`tests/test_drift.py`) runs in `uv run pytest -q`.

---

### `.claude/settings.json` (always-on hooks) and `config/driver/claude-settings.json`

**Analog:** `.claude/settings.json` (JSON, 2-space indent, `enabledPlugins` map). Add sibling key:
```json
"hooks": {
  "PreToolUse": [
    {"matcher": "Edit|Write|MultiEdit|NotebookEdit",
     "hooks": [{"type": "command",
                "command": "uv run --frozen python -I -m reverseapoc.hooks pre-tool-use --layer always"}]}
  ]
}
```
No `onFailure` key here (RESEARCH: older CLI may drop the handler). Driver file: matcher `*`, `--layer matching`, `"onFailure": "block"`, `enabledPlugins` overrides `"security-guidance@claude-plugins-official": false` (and other Stop-hook plugins). No `mcpServers`.

---

### `.claude/skills/watcom-decomp/SKILL.md`

Owner authors with `superpowers:writing-skills` (D-19). Shape reference only: frontmatter of `.claude/skills/unlazy/SKILL.md`. Sections fixed by D-19; command names must equal the attempt wrapper verbs. `tests/test_skill.py` checks every path/verb named exists (pattern: `tests/test_hygiene.py` needle lists, below).

---

### `land.py` / `check.py` DI-06 provenance

**Analog:** `land.write_landed` L167-176 (refuse inside orig, then atomic write) and `compiler.py` L165-206 (JSON stamp written atomically, "a torn, unreadable or wrong-shaped stamp is a miss"). Copy the stamp read/validate-or-miss pattern for the land provenance stamp and the stale-object refusal.

## Shared Patterns

### CLI verb registration
**Source:** `tools/reverseapoc/cli.py` L1074-1136, L1139-1178. **Apply to:** `gate`, `drive`, `attempt`, `context`.
- Write `_cmd_<verb>(args) -> int` and `_add_<verb>_command(sub)` with `sub.add_parser(name, help=...)`, `p.set_defaults(func=_cmd_<verb>)`; call it in `build_parser` after `_add_land_command(sub)`.
- Add the new error class to `_ERRORS` (L1139); `main` turns it into `reverseapoc <cmd>: error: ...`, exit 1. Verbs with 0/1/2 semantics (gate, attempt check) wrap like `_cmd_check` and return `EXIT_TOOL`.
- Update the module docstring verb list (cli.py L1-3).
- Output: `print(json.dumps(x.to_json(), indent=2) if args.json else x.format())`; results are frozen dataclasses with `to_json()`/`format()`.
- Long call sites use `# fmt: skip` aligned continuation (cli.py L888-891).

### Errors
`class XError(ValueError)` per module (check.py:96). Messages name the file and the fix command (check.py L870-871).

### Atomic writes
Every committed or generated file goes through `fileio.write_atomic` (after DI-18). Never `Path.write_text` for outputs.

### No game bytes in committed data or test output
status.csv, attempts.jsonl, decomphub.progress.json, report.json: addresses, names, statuses, counts only. Game-derived packs/listings/transcripts only under `build/driver/`. Results print VAs and SHA-1s, never bytes (land.py docstring L17-18).

### Tests
- **Synthetic first:** import `from conftest import REPO_ROOT, ...`; `from reverseapoc.cli import build_parser, main`; assert `main([...]) == 0` and inspect `capsys.readouterr().out` (`tests/test_cli.py` L1-27).
- **Real-file:** module docstring stating what it needs and that it asserts on names/VAs/SHA-1s only; skip helpers `requires_objdiff()`, `requires_runner()`, `ORIG_DIR` (`tests/conftest.py` L36-77; `tests/test_check_real.py` L1-35). New helper if needed: `requires_docker()` in conftest, same style (`shutil.which` + `pytest.skip` with the install hint).
- **Subprocess end-to-end (hooks, fakeclaude):** `tests/test_githooks.py` L1-45: `shutil.which`, `pytestmark = pytest.mark.skipif(...)`, and the `_Env(dict)` with a short `__repr__` so failing asserts never print the user's environment. Use `sys.executable -I -m reverseapoc.hooks` with JSON on stdin.
- **Fake tool:** `tests/watcomtree.py` `FakeCompiler` is the precedent for a stand-in executable; `tests/fakeclaude.py` replays `tests/fixtures/stream/*.jsonl` (synthetic events, no game bytes).
- **Doc/config needles:** `tests/test_hygiene.py` L120-160 (`needles` tuples, `assert [n for n in needles if n not in text] == []`). Use for the skill test, README progress URLs, `.dockerignore` (`test_hygiene.py:30` parametrize on extensions: add `IMG`, `CUE`, `mdf`).
- **Drift test (`tests/test_drift.py`, CI, no game files):** read `config/<exe>/status.csv`, `functions.csv`; for each `src/<exe>/*.c` call `check.source_marks(text, rows)` and assert matched rows == `defined`; LF-normalised sha256 per matched unit == `source_sha256`; `progress.derive(...)` == committed outputs.

### Container boundary
`check`/`gate` need objdiff-cli: run as `docker compose run --rm build uv run reverseapoc ...` (`check.CONTAINER_HINT`; compose mounts `../orig:/work/orig:ro`, `../third_party:/work/third_party:ro`, `docker/compose.yaml` L16-20). Host and container suites never run together (shared build/test-cc).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `tools/reverseapoc/streamjson.py` | utility | streaming parse | No stream-JSON consumer exists; only `check.match_percent` parses foreign JSON. Use RESEARCH Pattern 1 (pure classify). |
| Treemap SVG writer in `tools/progress.py` | utility | transform | No SVG output in repo; stdlib squarified or slice-and-dice (Claude's discretion). |
| Look-alike similarity (contextpack) | utility | transform | No opcode-sequence similarity code; `score.Features` is closest input. |
| `.claude/skills/watcom-decomp/SKILL.md` | doc | - | Owner-authored; only unlazy frontmatter as shape. |
| `docs/listings.md`, `docs/DECOMPHUB_VERIFICATION.md` | doc | - | Free text per D-31/D-33. |

## Metadata

**Analog search scope:** `tools/reverseapoc/`, `configure.py`, `tests/`, `.github/workflows/`, `.claude/`, `docker/compose.yaml`
**Files scanned:** ~20
**Pattern extraction date:** 2026-10-24

## PATTERN MAPPING COMPLETE

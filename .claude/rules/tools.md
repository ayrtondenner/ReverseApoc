---
paths:
  - "tools/**"
  - "tests/**"
  - "configure.py"
---
# Python tooling

- Python 3.14 pinned via `.python-version`; manage with uv (`uv run`, `uv sync --locked`).
- Test-driven: write the failing pytest first, then the code. `uv run pytest -q` and
  `uv run ruff check .` must pass before claiming completion.
- No third-party dependency without a reason recorded in `docs/tools.md`.
- Tooling under `tools/` is GPLv3 (see `docs/legal.md`); keep copyright headers of files derived
  from KKND-Decomp (CC0) and Theme Hospital decomp (GPLv3).
- Tests never embed game bytes; real-file tests skip unless `orig/` is present.
- Keep nesting shallow: split nested loops into small generators or helpers and skip cases
  with an early `continue`.
- No bare binary-format offsets: name each one after its spec field (e.g. `_REC_NAME = 33`)
  and derive related values from it (`_MIN_RECORD = _REC_NAME + 1`).
- A refactor keeps behaviour: pin it with tests first, prove they fail when the code is
  broken, and run `/code-review` again after `/simplify` or `code-simplifier`.
- Details and examples: `docs/coding-style.md#python-tooling`.

## YAGNI: scope, not effort

Applies to planning and writing Python tooling (`tools/**`, `tests/**`, `configure.py`). Never
to C or headers wherever they live (`src/`, `include/`, driver view units, the C fixtures under
`tests/fixtures/`), matched or not (see src.md). In review it is a lens (last bullet), never a
reason to read less.

- Build only what the task or plan asks for now. No option, flag, config key, parameter,
  abstraction (a protocol, base class or factory with one implementation), layer or "for later"
  code nobody asked for. Splitting a function into small helpers to keep nesting shallow is not
  a layer. If you see something useful out of scope, note it in one line in the final report
  and don't build it.
- Existing first. Reuse the helper, module or shape the neighbouring code uses, the way it uses
  it. No new dependency to save a few lines (and none without a reason in `docs/tools.md`).
- One solution. Deliver one approach, not a menu of alternatives.
- YAGNI is about WHAT gets built, never about the care taken. Every bullet above still applies,
  and none of this is cut:
  - the failing pytest first;
  - `uv run pytest -q` and `uv run ruff check .` green, in the container too (CLAUDE.md's
    Done gate);
  - a refactor pinned by tests first;
  - binary-format offsets named after their spec field and derived from it;
  - error context added in one place, never a silent `except`;
  - validation at boundaries (input files, offsets and sizes read from the binary);
  - real-file tests that skip without `orig/`, and no game bytes in tests;
  - licence and copyright headers;
  - the callers, tests and fixtures the change breaks.
- Not building is not not thinking. Before editing, read the code the change touches and all
  its callers.
- Review: YAGNI is something to look for (a speculative abstraction or an unrequested option is
  a minor finding), not a reason to review less.

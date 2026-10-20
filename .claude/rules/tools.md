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

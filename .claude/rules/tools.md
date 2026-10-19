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

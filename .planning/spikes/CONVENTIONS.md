# Spike Conventions

These are the patterns and stack choices established across spike sessions. New spikes follow
them unless the question requires otherwise.

## Stack

- Python stdlib only, run with `uv run python .planning/spikes/NNN-name/<script>.py`. The
  scripts live in the repo, so they must pass `uv run ruff check .`.
- Import `reverseapoc` only to cross-check it (`reverseapoc.le`) or for shared inputs
  (`targets.load_manifest`, `iso9660.ISO9660` for the disc image). Never take a fact from the
  module under test as its own proof.

## Structure

- `.planning/spikes/NNN-name/README.md` with spike frontmatter, plus one script per question.
  Side probes that explain a surprise get their own file (for example
  `001/extender_chain.py`, `003/followup.py`).
- The independent raw LE reader is `001-le-pages-and-fixups/rawle.py`. Later spikes load it by
  path with `importlib.util` and register it in `sys.modules` before `exec_module`, because
  dataclasses need it there.

## Patterns

- One `PASS/FAIL <file> <claim> <detail>` line per claim, `ALL PASS` or `N FAILED` at the end,
  and exit 1 on any FAIL. Expected values sit in an `EXPECTED` dict copied from the research
  they confirm.
- Prove the checker can fail: run once with a planted wrong expectation (001) or with
  reassembly mutants (002) and record what is and is not caught.
- Game data never leaves the script. Output is limited to offsets, lengths, counts, booleans,
  trailer positions, the first 4 trailer bytes and SHA-1s. Comparisons happen inside the
  script, and a match is reported by name and position, never by value.
- Read orig/ and the game install read-only, and read the disc image in memory. Write nothing.

## Tools & Libraries

- `struct`, `hashlib`, `zlib` (CRC32, Adler-32), `tomllib` (for `[[cd_builds]]`, which
  `load_manifest` does not read) and `importlib.util`.

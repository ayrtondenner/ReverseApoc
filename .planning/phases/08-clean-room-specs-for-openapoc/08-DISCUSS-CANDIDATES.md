# Phase 8: candidates for /gsd-discuss-phase 8

Items found before Phase 8 starts. Each one is a question for the discuss step, not a decision.

## Differential emulation as a rung on the spec ladder (2026-11-18)

- **Todo:** `.planning/todos/pending/differential-emulation-specs.md` (`area: specs`).
- **Idea:** a headless emulator harness, such as Unicorn, calls an original function with a spec's
  scenarios and compares the result with what the spec says. Byte-matching proves bytes, not
  behaviour.
- **Where it fits.** SPEC-01's ladder already reads `drafted -> cited -> backed-by-matched-code
  -> dosbox-verified -> reviewed-by-openapoc`. Two options for discuss:
  - a new `emulator-verified` rung beside `dosbox-verified`;
  - the automated way to reach `dosbox-verified`, in which case speclint's "a `dosbox-verified`
    claim without a test" check (SPEC-02) would accept an emulation test.
- **Cost.** L. It adds a new dependency (Unicorn), which needs a row and a reason in
  `docs/tools.md`.
- **Sources:** docs/research/notes-ideas-tooling-reproducibility.md #10 and
  docs/research/notes-ideas-llm-decomp-research.md #6.
- **Owner, 2026-11-18:** it belongs to the existing Phase 8 (clean-room specs), not a new phase.

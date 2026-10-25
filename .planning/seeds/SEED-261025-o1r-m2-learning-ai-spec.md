---
id: SEED-261025-o1r
status: dormant
planted: 2026-10-25
planted_during: Milestone 1, Phase 6 (Reporting and agent pilot)
trigger_when: Milestone 2, once the Learning AI functions are matched (after or alongside the full decomp)
scope: medium
---

# SEED-261025-o1r: Learning AI spec and documentation from the full decomp

## Why This Matters

The owner's reasoning, from 2026-10-25:
- The original Learning AI is known to be buggy.
- The goal is to document how it was implemented and why it is bugged, so OpenApoc developers can choose to fix the original design or build their own AI.
- That is why the work waits for Milestone 2 and the full decomp, not Milestone 1.

The result updates the Milestone 1 specs and `docs/findings/learning-ai.md` (Phase 8, SPEC-10), saying what works and what is bugged in the original.

## What Is Known Now (2026-10-25)

These are unmatched leads, not facts.

**The code is in our build.** Both EXEs name `TACDATA/EXPERIEN.DAT`, `BRAIN.DAT` and `WEAPEXP.DAT`. UFO2P also names the `BRAIN0.DAT` and `WEAPEXP0.DAT` defaults. TACP has an "Experience Processing" string.

**Tier 1, file I/O and reset.** About 10 small functions, roughly 2.3 KB:
- UFO2P: `func_000A5F40`, `func_000A6040` and `func_000A61E0`. They use plain `fopen`/`fread`/`fwrite`, and `func_000A6040` also uses `_dos_findfirst_`.
- TACP: `func_00078FE0`, `func_00079050`, `func_0009D140`, `func_0009D1D0`, `func_0009F680` and `func_0009F700`.

**Tier 2, the learning update.**
- `func_0009FA40`: 3,211 bytes, reads `EXPERIEN.DAT`, uses floating point (calls `__CHP`).
- Its helpers: `func_0009F8A0`, `func_000A06D0` and `func_000A0850`.

**Tier 3, how the tactical AI consumes the tables.** It is reached through global data, not the file names, so its size is unknown.

**Mission start and end callers:** `func_00014AF0` and `func_000B20B0`.

**Community claims to confirm or refute** (OpenApoc Discord and UFOpaedia):
- On load, the saved AI state is never restored; the files are refilled from the `0` defaults.
- A missing default file breaks file creation, because the code reads the default file's size first.
- The "needs real disc sector positions" theory. The plain fopen/open calls point against it.
- The "1.03 has a working AI" claim, which may trace to one hacked disc.
- Skin's unverified DeepSeek summary of TACP: Q-learning-like weight tables (`shot_section[25][12]`, `long_section[25][25]`) adjusted by a `calc_brain` routine.

## When to Surface

**Trigger:** Milestone 2, when the Tier 1-3 functions are matched.

## Scope Estimate

**Medium** once the code is matched. The Tier 2 float function and the Tier 3 consumers are the hard parts.

## Breadcrumbs

- The scan that found the references is a scratch script from 2026-10-25, not committed. It used string fixups plus direct `call` targets, with boundaries from `config/<exe>/functions.csv`.
- `docs/findings/learning-ai.md` (created in Phase 8).
- UFOpaedia "Learning AI" (rev 112726) and "Known Bugs (Apocalypse)" (rev 124000).

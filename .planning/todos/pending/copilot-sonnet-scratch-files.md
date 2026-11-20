---
title: Copilot Sonnet 5.5 writes scratch files; its prompt, quota figures and arm status
created: 2026-11-17
area: harness-copilot
files: tools/reverseapoc/session.py, config/driver/quota.toml, config/driver/backends.toml
source: runs 20261116-copilot2 to 20261116-fable-ab
---

# Sonnet tries files outside its write allowlist in most sessions

Copilot Sonnet 5.5 tried `plan2.json`, `giveup.json.tmp`, `giveup2.json`, `giveup.json2` and
`plan.json.tmp` across its sessions on 2026-11-16. Copilot's rules denied each, and since the
owner ruling of 2026-11-16 only the session ends, but every such session is spent: Sonnet
had 11 recorded sessions that day, 1 matched (`tacp func_000A68E0`, run 20261116-copilot2) and
10 gave up, all 8 of the A/B among them.

**Do:**
- Tell it in the session prompt (`session.copilot_prompt`) or the watcom-decomp skill which
  files it may write and that it must write `plan.json` and `giveup.json` in place, with no
  temp or numbered copies. A skill change goes through superpowers' writing-skills.
- Replace quota.toml's estimate of 40 credits with the measured figure: about 24 to 35 credits
  a session on 2026-11-16 (191.8 over 8 sessions in the A/B; 31 and 35 earlier).
- Decide whether the 60-credit per-session cap and the arm itself stay, from a short held
  run after the prompt change.

**Done when:** a Sonnet session no longer writes outside its allowlist in a short run, and
quota.toml carries its measured cost.

## Status (2026-11-18)

Status (batch 2026-11-18, U5): prompt forbids scratch copies; quota.toml Sonnet = 25.4 credits/session (11 records). Left: a short Sonnet validation run (credits), and the owner's keep/drop ruling on the arm.

## Status (2026-11-20): waiting on the owner's ruling

Rechecked at d893b5b7 (the Copilot prompt-margin change). The first two **Do** items still hold:
`session.copilot_prompt` ends with `_COPILOT_WRITES` (write each file in place, no `.tmp`,
numbered or other copy), pinned by `tests/test_copilot.py::test_copilot_prompt_forbids_scratch_copies_of_the_session_files`
(passes, as do the 4 `-k copilot` tests in `tests/test_session.py`). quota.toml carries 25.4
credits a session. Nothing in the code or config is left to change without a run.

No Sonnet session has run since the prompt change. `progress/attempts.jsonl` has the same 11
`copilot-sonnet-5-5` records as on 2026-11-18, all from 2026-11-16 (the main checkout's
working copy too, during the 2026-11-20 drive). No run directory under `build/driver/` after
20261116 has a Copilot Sonnet lane. So the "Done when" check, a short run with no write outside the
allowlist, has not happened, and only a paid session can do it.

Measured on 2026-11-16, before the prompt change (run records' stop details):

- Scratch writes stopped or ended sessions in runs copilot2 (`plan2.json`), copilot3
  (`plan.json.tmp`, `giveup.json.tmp`) and mixed4 (`plan.json.tmp`, `plan2.json` twice). In
  fable-ab the run stopped on a wrapper temp file (`checks/.0002.json.<hash>.tmp`), which was
  fixed under `completed/interrupted-check-temp-file.md` and is not this todo.
- The 10 GAVE_UP records give real reasons in 8 cases (register allocation 2, block layout 3,
  flags 1, call convention 1, instruction idiom 1). The other 2 are check timeouts (container
  over 580 s, nothing measured). The 1-in-11 rate reflects Sonnet's matching on those
  functions, not only the scratch writes. The A/B picked ufo2p `func_000A5980` 4 times.
- Credits per match: Copilot Sonnet 279.9 for 1 (11 sessions); Copilot Haiku about 45
  (273.6 for 6, 123 sessions). Copilot Pro has 1,500 credits a month: about 59 Sonnet sessions
  or about 675 Haiku sessions.

### Owner ruling needed: the validation run, the cap, and whether the arm stays

- **A. One short validation run, then decide (recommended).** Run one Copilot Sonnet lane of 4
  sessions (`max_workers = 4`, near-miss lane, different functions), about 100 credits
  expected and 240 at most under the 60 cap, about 7% of the month. If any session writes
  outside its allowlist, the prompt rule failed: park the arm and reopen this as a skill-level
  fix (through writing-skills). If none does, close this todo, keep the 60 cap (the backends.toml
  note: the costliest measured session was 47.6) and keep the arm behind Copilot Haiku in
  priority, since Haiku costs about a sixth as much per match.
- **B. Park the arm now.** Leave its config in place but schedule no Copilot Sonnet lane, and
  spend Copilot credits on Haiku. Close this todo with the prompt rule unvalidated, and make a
  4-session check like A's the first step of any later Sonnet night.
- **C. Keep the arm with a lower cap (30 to 40 credits).** This cuts the cost of a spent
  session, but the measured sessions ran 16.6 to 36.4 credits (47.6 for one the audit stopped),
  so a 30 cap would end some sessions of normal length. A validation run is still needed.

Recommendation: A. The sample is 11 sessions, and 2 of the 10 give-ups measured nothing, so
the data cannot settle the arm either way. Four sessions settle the scratch-file question for
a bounded spend, and the cap keeps it bounded.

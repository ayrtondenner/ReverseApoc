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

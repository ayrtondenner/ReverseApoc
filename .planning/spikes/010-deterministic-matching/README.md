---
spike: 010
idea: deterministic-matching
name: deterministic-matching
type: standard
validates: "Given Tier 1's unmatched must-match functions, when a converter (assembly to C89) plus a scripted variant search compiles every candidate with the real wcc386 10.6 and judges it like check, then 60%+ of a fixed stratified sample byte-matches (or 80%+ at any slope) and all of Tier 1 compiles and compares in 10 minutes or less"
verdict: PARTIAL
related: [008, 005, 004]
tags: [converter, lifter, batch, variants, flags, filler, oneatx, d-12, d-33, phase-7]
---

# Spike 010: deterministic matching (converter first, Claude sessions last)

## What This Validates

Given Tier 1's 886 not-matched must-match functions, when a converter turns each function's
assembly into C89 and a scripted variant search tries Watcom's known sensitivities, with every
candidate compiled by the real wcc386 10.6 and judged the way `check` judges, then:

- GO: 60% or more of a fixed, stratified, seeded sample matches byte for byte and the curve is
  still climbing, or 80% or more; and all of Tier 1 compiles and compares in 10 minutes or less;
- NO-GO: under 30% with a flat curve, or throughput that cannot reach the target;
- PARTIAL: anything in between, with what blocks it.

Time box: about 5 working days. This session used about half a working day of it (curve points
19:59 to 20:36 UTC on 2026-11-01, plus setup). See "Results" for why the run stopped there.

## Verdict

**PARTIAL.** By the proposed thresholds, the converter as built is a NO-GO. Throughput is a
clear GO. The curve is not flat at the end, but its one climb came from flags, not from the
converter.

| Question | Result |
|---|---|
| Q2 throughput | **VALIDATED.** All of Tier 1 compiles and is judged in about 10 s on the host and 25 s in the container (target 600 s). |
| Q3 converter | **Below the NO-GO line.** After 7 iterations, 20 of 200 sampled rows (10.0%) are exact; 0 of 100 are exact at 256 B and up. |
| Q4 variant search | **3 more matches.** With Q3 that makes 23 of 200 (11.5%), at 0.10 s per variant. |
| Q5 gate fit | **Passed for 3 of 5.** Three converter matches pass the real `check` (objdiff 100%, relocation check, both whole-EXE SHA-1s) and the C89 lint. Two failed on unit-context declarations. |

**The real finding is about flags, not the converter** (iteration 7, below). Watcom 10.6 puts
alignment filler after a function only under a `t` optimisation (`-ot`, `-oneatx`). 532 of the
886 not-matched Tier 1 rows end in filler under the committed `*` default, which has no `-o`.
Every matching attempt on those rows, by converter or by agent, therefore compiles with flags
that are very likely wrong.

## Research

The reuse survey (Q1) is below. Prior spikes this builds on:
- **004**: wibo runs 10.6.
- **005**: objdiff is a score, not the gate.
- **008**: the PARTIAL backlog is mostly a flags problem; 49 of 58 sweep hits land on
  `-4r -oneatx`.

## How to Run

All output goes to the gitignored `build/spike-010/`. The scripts hold no game bytes. They
import `reverseapoc` as the judge (`check.load_exe`, `defined_functions`, `with_relocs`,
`compare_bytes`, `compiler.check_gate`/`build_argv`). That departs from CONVENTIONS.md's
"cross-check only": the brief requires the same relocation masking as `check`.

```
uv run python .planning/spikes/010-deterministic-matching/sample.py        # seeded sample
uv run python .planning/spikes/010-deterministic-matching/control.py       # harness control
uv run python .planning/spikes/010-deterministic-matching/throughput.py    # Q2, host
docker compose run --rm -T build bash -lc "uv sync --locked -q && uv run python \
  .planning/spikes/010-deterministic-matching/throughput.py --workers 1,4,12"   # Q2, container
uv run python .planning/spikes/010-deterministic-matching/run.py --label "..."  # Q3, one point
uv run python .planning/spikes/010-deterministic-matching/run.py --infer-flags "-4r -oneatx -s -fpi" --label "..."
uv run python .planning/spikes/010-deterministic-matching/variants.py --run <run> [--infer-flags CELL]  # Q4
uv run python .planning/spikes/010-deterministic-matching/q5_views.py      # Q5 views
uv run python .planning/spikes/010-deterministic-matching/filler_census.py # filler census
uv run python .planning/spikes/010-deterministic-matching/lift.py <exe> <0xADDR>  # one row's C, terminal only
uv run python .planning/spikes/010-deterministic-matching/dump.py <exe> <0xADDR> [obj]  # local probe, terminal only
```

## What to Expect

- `control.py`: `control: 57/57 exact`, and a mutant that fails.
- `run.py`: one curve line per set and bucket, appended to `build/spike-010/curve.jsonl`, plus
  the top failure groups.
- `variants.py`: extra exact matches and seconds per variant.

## Preconditions checked

- **No drive was running.** `ProcessLock(DRIVE_LOCK).try_acquire()` returned True. The lock
  file was empty, dated 2026-10-30. The live processes were VS Code `claude.exe` sessions and
  the isort language server; there was no `claude -p`.
- **Re-measured the brief's facts.** `uv run reverseapoc mechanics status --tier 1` gave
  `tier 1: 943 members, 57 matched, 76 partial, 810 unmatched`. `uv run reverseapoc stats`
  gave 66 matched functions by trailer and $5.13 per matched function. Opus by size: [0, 64)
  56 of 116 attempted matched, [64, 256) 4 of 25.
- **Sample** (`sample.py`, `SEED = 20261101`, 50 per bucket):
  - not-matched Tier 1 by bucket: <64: 107, 64-255: 332, 256-1023: 327, >=1024: 120 (886);
  - control: 57 matched (53 under 64 B, 4 at 64-255);
  - no held rows.

## Q1: reuse survey

One Explore agent read the four repositories through `gh api` only. It cloned nothing and ran
none of their scripts. Our `tools/` is GPLv3.

| Repo | Licence | Effect on us |
|---|---|---|
| brotchie/daggerfall-decomp | **none** (no LICENSE, API 404): all rights reserved | idea only; its match/omf/le tools say "adapted from KKND (CC0)", so take KKND's originals |
| matteo-pacini/theme-hospital-decomp | **GPL-3.0-or-later** for tools, configure.py, config/, docs (src/ and include/ excluded) | compatible: reuse or adapt |
| abdulahmad/NHL95PC | **none** (no LICENSE): all rights reserved; also commits WCC386.EXE and DOS4GW.EXE | idea only |
| Wyrelade/KKND-Decomp | **CC0-1.0** (its Open Watcom patch also falls under OWPL) | compatible: reuse |

| Repo | Tool | Kind | Verdict | Why |
|---|---|---|---|---|
| Daggerfall | tools/lift.py, lift_all.py | lifter, batch, grouping, choice-point search | idea | no licence. Its premise (`-od -d2`: every statement reloads operands from memory) does not hold for our `-4r` code, which keeps values in registers across statements. |
| Daggerfall | w10_frame.py, slot_plan.py, frame_order | frame-slot model (shell sort by size) | idea | no licence; models 10.0a `-d2` only |
| Daggerfall | structure.py | goto to structured C, kept only if it still matches | idea | no licence; the right second stage for a lifter |
| Daggerfall | settle_lifted.py | a function failing in its unit moves to its own file | idea | no licence; we hit the same unit-context effect (Q5) |
| Theme Hospital | tools/variants.py | beam search over source variants | **adapt** | GPLv3+; swap its objdiff score for our judge |
| Theme Hospital | tools/x86scan.py | treats fixup sites that are not operands as switch-table dwords | reuse | GPLv3+, small |
| Theme Hospital | check.py, cc.py, asm2src.py, standin.py | per-unit compile and check, asm stand-ins | adapt / idea | ours already does check; stand-ins are a policy choice (they are not decompiled) |
| NHL95PC | permute.py (+cexpr, permute_decls, scope_decls) | hill-climbing permuter, about 14 transform kinds | idea | no licence |
| NHL95PC | draft_causes.py, classify_diff.py | failure classes (register, slot, branch, tail, size) | idea | no licence; better grouping than our first-diff key |
| NHL95PC | wccre/ (unicorn-hosted WCC386 10.0 internals) | register-allocation and slot-sort probes | idea | no licence; its addresses are for 10.0 GA |
| NHL95PC | module_try.py | compile a whole segment so shared tails merge | idea | no licence; matches our filler and neighbour finding |
| KKND | tools/match.py, omf.py, le.py, find_functions.py | compile, cut, mask, compare | reuse (already derived) | CC0; check.py and relocs.py derive from it |
| KKND | auto_families.py | lifts stub families (ret const, forward) | reuse / adapt | CC0; covers part of our <64 B bucket |
| KKND | owpatch/ | Open Watcom patched to act like 10.x | skip | we have the real 10.6; OWPL question |

Their numbers:
- **Daggerfall**: 2,297 game functions, 100% in about a week. Its first batch lifted 23% in
  about 2 s, and 2,091 had matched before agents took the last ~206.
- **Theme Hospital**: 2,938/2,938, counting asm stand-ins.
- **NHL95PC**: 977/1,084 (90.1%).
- **KKND**: stalled at 13%. Its PLAN.md blames code-generator gaps between Open Watcom and real
  Watcom 10.x, not one agent per function.

Watcom sensitivities they document, to verify here before relying on them:
- the larger operand tree is evaluated first;
- 10.6 sorts frame slots per code chunk by size;
- register allocation sorts by loop-weighted savings, so one temporary moves registers across
  a whole function;
- casts change compare width;
- identical function tails are merged across a file, even without `-o`.

## Q2: batch throughput (VALIDATED)

`throughput.py` compiles 600 one-function stubs (one per Tier 1 member, each with its unit's
cflags rule) and judges each one. It gates once per batch (`compiler.check_gate`), then runs
`build_argv` commands in a thread pool.

| Where | Workers | Compile wall | Judge | s/function | Tier 1 (943) projected |
|---|---|---|---|---|---|
| host (win32, 12 CPUs) | 1 | 9.97 s | 4.27 s | 0.0237 | 22.4 s |
| host | 4 | 2.24 s | 4.37 s | 0.0110 | 10.4 s |
| host | 12 | 1.89 s | 4.35 s | **0.0104** | **9.8 s** |
| container (wibo, 12 CPUs) | 1 | 84.35 s | 5.41 s | 0.1496 | 141.1 s |
| container | 4 | 16.84 s | 5.62 s | 0.0374 | 35.3 s |
| container | 12 | 10.90 s | 5.12 s | **0.0267** | **25.2 s** |

- **Compile time.** One compile takes 0.014 s on the host and 0.088 s under wibo.
- **Gate cost.** A `check_gate` (hash and banner) in a fresh stamp directory took 0.016 s,
  and a second call took 0.016 s too. Inside a batch, with the existing stamp under
  `build/cache/`, it took 0.000-0.004 s, because that stamp already re-hashes only on a stat
  change. The per-compile gate cost (D-13) is therefore about one compile's
  time; hashing once per batch saves it but was never the bottleneck.
- **Judging.** Single-threaded, it takes about 0.007 s per function and is the bigger share on
  the host.
- Daggerfall measured 0.08 s per function. We are 3 to 8 times faster.

## Harness control

`control.py` compiles the 42 committed units that hold the 57 matched Tier 1 functions through
the batch path:
- result: `control: 57/57 exact from 42 units; compile failures 0; compile wall 0.27s`;
- mutant: `extern int` changed to `extern short` in ufo2p/u_000105d0, which fails 1 of its 1
  control functions;
- so the judge agrees with `check` on every matched function, and it can fail.

## Q3: converter v0 and the fix loop

### The converter

`lift.py` (about 1,000 lines) decodes a row with capstone and builds basic blocks. It runs each
block symbolically: a register holds a C expression tree. From there it emits C89:
- **Arguments.** Register parameters use the Watcom order `eax, edx, ebx, ecx`, taken from
  liveness at entry. Stack parameters come from `ret N`.
- **Locals and globals.** Stack slots become locals typed by access width. Globals become
  `extern char D_<target>[]`, read through casts or as `((T *)D)[i]`.
- **Calls.** Argument counts come from the callee's signature (computed for every callee, with
  cycles allowed) and the call site's own register evidence.
- **Control flow.** Branches become `if (c) goto L;`. Tail jumps become `return f(args);`.
  `cdq` or `sar 31` followed by `idiv` becomes `/` and `%`.
- **Variables and types.** Variables are created only at merge blocks. `char`/`short`
  parameter and return types come from byte and word reads.
- **Return type.** It is `void` unless a caller in the EXE reads `eax` after the call
  (a cached census over all game rows).

Anything else raises "unliftable: reason", which counts as its own failure group.

### The curve

`build/spike-010/curve.jsonl` gets one point per run. Cells read **exact / exact-or-filler-cut**,
where filler-cut means our bytes match once the original row's trailing filler is cut off.
There are 50 sampled rows per bucket; the control has 57 rows.

| UTC | Iteration | <64 | 64-255 | 256-1023 | >=1024 | Sample (200) | Control (57) | Lifted |
|---|---|---|---|---|---|---|---|---|
| 19:59 | 0: v0 | 2/2 | 0/0 | 0/0 | 0/0 | **2** (1.0%) | 23 | 54 |
| 20:01 | 1: tolerant callee signatures, call-site args, stack params | 2/2 | 0/0 | 0/0 | 0/0 | 2 | 31 | 55 |
| 20:03 | 2: idiv/div, tail jumps, flags into fall-through, filler-cut judge | 2/12 | 0/0 | 0/0 | 0/0 | 2 (12) | 32 | 65 |
| 20:05 | 3: calls read their args in liveness, sar-31 sign extension | 2/11 | 0/1 | 0/0 | 0/0 | 2 (12) | 32 | 84 |
| 20:07 | 4: args = live at entry, narrow char/short types | 2/14 | 0/1 | 0/0 | 0/0 | 2 (15) | 32 | 84 |
| 20:09 | 5: single-predecessor blocks inherit expressions (compute-once on / off) | 2/14 | 0/1 | 0/0 | 0/0 | 2 (15) | 32 / 30 | 84 |
| 20:13 | 6: array index idiom, `void` unless a caller reads eax (on / off) | 2/14 | 0/1 | 0/0 | 0/0 | 2 (15) | 32 / 31 | 84 |
| 20:32 | **7: default-rule rows ending in filler take `-4r -oneatx -s -fpi`** | **18/18** | **2/2** | 0/0 | 0/0 | **20 (10.0%)** | 32 | 84 |
| 20:32 | 7 alt: the same with `-4r -ot -s -fpi` | 14/14 | 1/1 | 0/0 | 0/0 | 15 | 32 | 84 |

Iterations 1-6 tackled the biggest refusal or diff group each time:
- **Lifted climbed** from 27% to 42% of the sample.
- **Strictly exact stayed at 2/200.**
- **Filler-cut grew to 15.** Those rows were byte-correct except for the row's trailing
  filler.

### Iteration 7: the flags finding

The trailing filler is the key, so I tested it directly. Our C for tacp 0x000A68B0, followed by
a second function in the same file, was compiled under every flag cell.

| Cell | Next function at | Exact |
|---|---|---|
| `-4r -s -fpi` (the `*` default) | 37 (no padding) | no |
| `-4r -ox -s -fpi` | 37 | no |
| `-4r -os -s -fpi` | 36 (tail-merged) | no |
| `-4r -oa` / `-ol` | 37 | no |
| **`-4r -ot -s -fpi`** | **48** (padded to 16) | **yes** |
| **`-4r -oneatx -s -fpi`** | **48** | **yes** |

The test also showed what does not cause padding:
- Under the default flags no kind of next function makes Watcom pad. I tried an empty one, one
  with a loop, one with a switch, and a static.
- An empty next function gets its `ret` merged into ours.

So filler after a function is evidence of a `t` optimisation, or of an object boundary.

The census (`filler_census.py`) and the matched rows support that:

| Bucket | Not matched | End in filler, default rule | End in filler, `-o` rule |
|---|---|---|---|
| <64 | 107 | 73 | 2 |
| 64-255 | 332 | 207 | 9 |
| 256-1023 | 327 | 188 | 8 |
| >=1024 | 120 | 64 | 3 |
| **all** | **886** | **532 (60%)** | 22 |

Of the 66 matched functions (both status.csv files):
- **none** ends in filler under the default rule (0 of 48);
- 4 of the 18 under `-o` rules do.

So it is very likely that agents and the converter have been compiling 60% of what is left
under wrong flags. This extends spike 008's "the partial backlog is a flags problem" from the
partials to most of Tier 1.

### Failure groups left (iteration 6, sample)

These are refusals, about 58% of the sample:

| Count | Group |
|---|---|
| 22 | high-byte registers (`ah`/`dh` byte variables) |
| 16 | stack arrays or structs addressed by arithmetic |
| 15 | switch jump tables |
| 10 | address of a stack slot |
| 9 | setcc |
| 7 | stack-convention callees |
| 7 | sbb |
| 7 | esp read |
| 6 | compile E1151 |
| 5 | x87 |
| 4 | movsd struct copies |

What remains among the compiled rows is register choice and save-set differences (`push` sets
that differ). That is the register-allocation class, which KKND and NHL95PC also fought.

## Q4: scripted variant search

`variants.py` takes every compiled, non-exact sample row. For each it tries the combinations of
5 choice points:
- return type (as inferred, `void`, `int`);
- compute-once or re-emit;
- narrow types on or off;
- array idiom on or off;
- local declaration order as found or reversed.

The real compiler judges every distinct variant.

| Base run | Rows | Distinct variants | s/variant | New exact | Already filler-cut |
|---|---|---|---|---|---|
| iteration 6b (`20261101-202524`) | 76 | 514 | 0.099 | **3** (all `void` forced) | 13 |
| iteration 7 (`20261101-203117`, `-oneatx` inferred) | 58 | 470 | 0.104 | **3** (the same three) | 0 |

- **Final sample result: 23/200 (11.5%) strictly exact.**
  - <64: 21/50 (42%)
  - 64-255: 2/50 (4%)
  - 256-1023 and >=1024: 0/100
- **Cost.** About 0.1 s and one compile per variant, roughly 30 variants per extra match
  (514 variants for 3 matches), and no model.
- **Near-misses.** Only 1 non-matching row reached 90 or more. The rest are far off, so this
  search space is not where the remaining matches are.

## Q5: gate fit

`q5_views.py` copies the whole committed `src/` to `build/spike-010/view-N/src/` and replaces
the one `INCLUDE_ASM` marker with the converter's C, scaffolding the unit in the view when the
committed tree has none. It then runs in the container:
- `check <exe>/<unit> --src <view>`: the real check, which writes to build/check-custom only;
- `lint <file>`.

On the host it runs `readlint`. `gate` itself was not run: it writes status.csv and the
progress feed.

| View | Function | check | lint | readlint (expected to fail) |
|---|---|---|---|---|
| 1 | ufo2p func_000520A0 (u_00052080) | compile failed (exit 2) | 6 errors | not run |
| 2 | ufo2p func_000520E0 (u_00052080) | compile failed (exit 2) | 6 errors | not run |
| 3 | tacp func_000A6000 (u_000a5c10) | **OK**: objdiff 100%, reloc ok, bytes ok; splice OK UFO2P `e7488bf3...` and TACP `48ef0096...`; exit 0 | **exit 0** | RL01 x9, RL02, RL05 x2, RL06 x2 |
| 4 | tacp func_000A6080 (u_000a6080) | **OK** (as above), exit 0 | **exit 0** | RL01 x9, RL02, RL05 x2, RL06 x3 |
| 5 | ufo2p func_0002F720 (u_0002f460) | **OK** (as above), exit 0 | **exit 0** | RL01 x9, RL02, RL05 x2, RL06 x2 |
| 6 | tacp func_0004D220 (u_0004d220), `-oneatx` from a temporary `--cflags` | MISMATCH: 66 bytes against an 80-byte row (length) | not run | not run |

- **Views 1-2 fail on declarations.** The unit already declares those globals with real types
  (`extern int D_000E12F0;`, `extern short D_00183A80;`), and the converter redeclares them
  `extern char D_X[]`. Putting converter output into an existing unit needs a declaration merge:
  reuse the unit's declarations and rewrite accesses to them. Daggerfall's `settle_lifted.py`
  answers the same problem.
- **View 6 fails on alignment.** In the real unit the next function is an `INCLUDE_ASM` stub,
  which emits no code. So nothing follows ours, Watcom aligns nothing, and our size is
  trimmed. The harness hid this because its pad function supplied the neighbour. A filler row
  passes `check` only when the next function is compiled in the same object, or when `check`
  accepts trailing filler up to the next 16-byte boundary at the end of our object. The second
  stays byte-safe: `land` keeps the original bytes there, and the whole-EXE SHA-1 still decides.
- **readlint, as expected.** Raw converter output fails RL01 (placeholder names), RL02 (no
  header comment), RL05 (raw offset casts) and RL06 (magic literals). It does not trip RL03 or
  RL04. readlint skips a unit with no matched row, so it ran with a view copy of `config/`
  whose status.csv marks the function matched.

## Results

### Projection onto the 886 remaining Tier 1 functions

With the converter as it stands plus the variant search, applying the sample rates per bucket:

| Bucket | Left | Converter rate | Converter matches | Left for agents |
|---|---|---|---|---|
| <64 | 107 | 42% | ~45 | ~62 |
| 64-255 | 332 | 4% | ~13 | ~319 |
| 256-1023 | 327 | 0% | 0 | 327 |
| >=1024 | 120 | 0% | 0 | 120 |
| **all** | **886** | **~6.5%** | **~58** | **~828** |

The tail at today's agent rates per session (Opus: <64 B 44/252 = 17.5%; 64-255 B
2/51 = 3.9%; nothing measured at 256 B and up, assumed no better than 3.9%):

| Bucket | Sessions needed |
|---|---|
| <64 | 62 / 0.175 ≈ 350 |
| 64-255 | 319 / 0.039 ≈ 8,200 |
| 256 and up | 447 / 0.039 ≈ 11,500 or more |
| **all** | **about 20,000** |

At `--max-sessions 180`, 20,000 sessions is **about 110 nights**, and those nights are the
whole schedule. The converter's own share is days of work, not weeks. Tier 1 is not reachable
in weeks on this path.

Two things the spike could not measure would change that projection:
- **Agent rates under corrected flags.** Agents may match far more often once 60% of the rows
  compile under the right flags. That is the next spike, not a guess to plan on.
- **The converter's plateau.** The biggest refusal groups (byte variables in `ah`, switch
  tables, stack structs) have not been worked yet. Iterations 1-6 show that lifting more rows
  does not by itself produce matches.

### Biggest risk

The 447 functions at 256 B and up (50% of what is left):
- the converter matched 0 of 100;
- Opus has no recorded attempt at that size;
- their failures are register allocation and frame layout, which needs either Daggerfall-style
  choice points with hundreds of compiles each, or agents.

### Why the run stopped early

The converter's curve was flat for six iterations: lifted rows climbed, matches did not. Then
iteration 7 showed that the lever is flags, which is a D-12/D-33 owner question, not converter
work. Continuing converter work before the flags are ruled would measure against the wrong
compiler settings for 60% of the rows. So the spike stops here with a smaller, sharper next
question.

### Surprises

- Watcom 10.6 aligns functions only under `-ot` / `-oneatx`, not under `-ox`, `-os`, `-oa`,
  `-ol` or no `-o` (measured above). So trailing filler is free per-row evidence for flags.
- An empty function after ours is tail-merged into our `ret`, even under the default flags.
- The register-variable style of C (Daggerfall's) gets byte-correct code for many tiny
  functions. Above 64 B it falls apart on register choice.
- `check` and the harness agree on all 57 matched functions. The harness is ready to reuse.

## Draft replan (not applied; the owner rules)

### Plans that change

- **07-39** (matching nights until Tier 1 is matched): paused until the flag census is ruled.
  Nights then run on corrected flags, and the stall rule measures them again from zero.
- **07-40** (readability nights): unchanged in purpose. It also takes converter-made units,
  whose readability is the whole job (RL01/RL02/RL05/RL06 on every one).
- **07-41** (phase gate): adds the `converter` match class to the sign-off figures and the
  cleanup-session audit (no restructured function without a passing gate run in its commit).

### New plans, in order

1. **07-46 flag census from filler (spike 011 first).** For each default-rule unit, take its
   filler evidence plus `check --sweep` on what has a candidate C, then propose per-unit cells
   through the existing D-12 queue (`flags propose`, container `flags regate`, owner
   `flags approve`). Measure the agent rate again on 30 sessions under corrected flags.
2. **07-47 batch harness in tools/.** Move `common.py` into `tools/reverseapoc/batch.py`, with
   TDD, a `reverseapoc batch` verb and the control test (57/57 plus a mutant) in pytest
   (real-file, skipped without orig/).
3. **07-48 filler and neighbour rule in check.** Option A: `check` accepts trailing Watcom
   filler up to the next 16-byte boundary when our function is the last code in our object and
   the unit's rule has a `t` optimisation. Option B: the converter and agents always compile a
   filler row together with its successor. The owner rules; option A changes the gate (see
   rulings).
4. **07-49 converter v1.** Declaration merge into existing units; byte variables in `ah`;
   switch tables (with Theme Hospital's GPLv3 `x86scan.py` adapted); stack structs and arrays;
   setcc and sbb idioms; NHL95PC-style failure classes (register, slot, branch, tail) in place
   of first-diff keys.
5. **07-50 variant search v1.** Adapt Theme Hospital's GPLv3 `variants.py` beam search over the
   converter's choice points, at most 600 compiles per function (Daggerfall's budget).
6. **07-51 cleanup session kind.** Gated whole-function replacement of matched code, with
   automatic revert and a try cap (rule text below).
7. **07-52 tail nights.** The existing driver, with `--workers 10 --max-sessions 180`, takes
   only what the converter and the search left. The pick order is smallest first, under
   corrected flags.
8. **07-53 readability nights.** 07-40's driver, over converter-made units.

### Rule text for gated restructuring (for CLAUDE.md and .claude/rules/src.md; not applied)

> A matched function stays byte-identical. Its C may be restructured (control flow, temporaries,
> declarations, types) only in a cleanup session (`drive --session cleanup`), as a replacement
> of the whole function in one commit, and only when `reverseapoc gate` passes on that commit
> in the container: objdiff 100% for every function the unit defines, the relocation check and
> both whole-EXE SHA-1s. The driver reverts the replacement automatically when the gate fails
> and records the try; after 3 failed tries a function is not offered to cleanup again until
> the owner clears it. No inline assembly, `#pragma` or flag change is allowed in a cleanup
> session, and renames and comments stay governed by the readability rules.

In `.claude/rules/src.md`, the line "Never restructure, simplify, reorder declarations, or
modernize a function that already matches" would become "...outside a cleanup session (see
CLAUDE.md); inside one, only as a gated whole-function replacement".

### Stats change

A fourth match class, **`converter`**, sits beside `unattended`, `human-hints` and
`human-written`:
- **Trailer.** It is set by a `Matched-By: reverseapoc lift` trailer, optionally with
  `Lift-Variant: <choice points>`.
- **Classing.** stats.py classes a commit by trailer, so a converter match never counts toward
  AGT-11's unattended figure. A converter match later rewritten by a cleanup session keeps its
  class, and the cleanup is reported as its own event.
- **Breakdowns.** `stats` prints the class split per size bucket, plus compiles per converter
  match.

## Owner rulings needed

1. **Thresholds.** Confirm or change the GO/NO-GO lines: GO at 60% exact with a climbing
   curve, or 80%+; NO-GO under 30% with a flat curve, or throughput that misses 10 minutes;
   PARTIAL in between. Measured here: 11.5%, a curve flat for six iterations and then a step
   from flags, and throughput at 10-25 s.
2. **Flags from filler.** Should trailing filler count as evidence for proposing a per-unit
   `t`-optimisation cell (D-12 queue, D-33 bar), and should spike 011 run the census plus an
   agent re-measure before any more nights?
3. **The filler rule in check** (07-48 option A or B). Option A changes what the gate accepts:
   trailing filler not produced by our object, guarded by `land` and the whole-EXE SHA-1.
4. **Converter output into src/.** May raw converter C land through the normal gate as
   unreadable C, with the `converter` class, as Daggerfall did? Readability then follows in
   07-40/07-53.
5. **The cleanup-session rule** (text above): wording, the try cap, and whether `#pragma`
   stays banned there too.
6. **Theme Hospital reuse.** Reuse Theme Hospital's GPLv3 `variants.py` and `x86scan.py`
   (adapt, keep headers), and take NHL95PC and Daggerfall as ideas only, since neither has a
   licence.

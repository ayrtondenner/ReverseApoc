---
spike: 011
idea: deterministic-matching
name: flags-from-filler
type: standard
validates: "Given Tier 1 rows whose original ends in Watcom alignment filler, when they are compiled under the inferred cell -4r -oneatx -s -fpi (with a following function so Watcom aligns) by spike 010's converter over all 886 not-matched rows and by parallel Claude subagents on a seeded 64 B+ sample, then the match rate rises against the committed rule, and the filler is evidence of the flags"
verdict: PARTIAL
related: [010, 008]
tags: [flags, filler, oneatx, alignment, converter, agents, subagents, d-12, d-33, check-length-rule]
---

# Spike 011: flags from filler

## What This Validates

Spike 010 (iteration 7) read trailing filler as evidence that a unit was built with a `t`
optimisation, because wcc386 10.6 aligns the next function only under `-ot`/`-oneatx`. This
spike measures two things on Tier 1's 886 not-matched rows:
- what correcting that buys for the converter and for agents;
- whether the filler really is flag evidence.

## Verdict

**PARTIAL.** The match rate rises sharply under the inferred cell, for the converter and for
agents. But **the filler is mostly not flag evidence.** It is mostly linker alignment of
original objects that each held one function. Three measurements show it:
- Of 51 converter matches under the inferred cell, 32 are byte-identical under the committed
  rule once the filler is cut, and only 13 differ in code.
- Every matched function in a "`t`-like" default-rule unit stays exact under `-ox` (29 of 29),
  but only 20 of 29 under `-oneatx`.
- Blanket `-oneatx` breaks 12 of the 66 functions already matched.

So the levers are:
1. **The gate's length rule** for trailing filler, or a unit recut. This is the bigger one, and
   it is a `check` change, not a flags change.
2. **A per-function `-oneatx` cell** where the code itself proves it. 13 converter rows and 5
   agent rows proved it here.

This corrects spike 010's "real finding" paragraph (a note is added there).

## How to Run

```
uv run python .planning/spikes/011-flags-from-filler/all_tier1.py      # converter, 886 rows x 4 arms
uv run python .planning/spikes/011-flags-from-filler/unit_census.py    # function-start alignment per unit
uv run python .planning/spikes/011-flags-from-filler/control_cells.py  # matched units under each cell
uv run python .planning/spikes/011-flags-from-filler/agent_sample.py   # seeded agent sample
uv run python .planning/spikes/011-flags-from-filler/judge_cli.py <exe> <0xADDR> <file.c>  # one attempt, both cells
```

`s011.py` imports spike 010's harness (`common.py`, the judge with check's relocation masking),
its converter (`lift.py`) and its `run.effective_rule` and `PAD`. Output goes to the gitignored
`build/spike-011/`. The scripts hold no game bytes.

## Part 1: converter over all 886 not-matched Tier 1 rows

`all_tier1.py`: 1,624 variants, 1,564 compiled. Lifting took 104.9 s, compiling 7.6 s, judging
15.0 s (2 min 13 s in all). The converter refused 480 rows.

| Arm | <64 | 64-255 | 256-1023 | >=1024 | All |
|---|---|---|---|---|---|
| committed rule | 6 | 0 | 0 | 0 | 6 |
| committed, `void` forced | 7 | 0 | 0 | 0 | 7 |
| inferred `-4r -oneatx -s -fpi` (filler rows, plus a pad function) | 39 | 12 | 0 | 0 | 51 |
| inferred, `void` forced | 33 | 11 | 0 | 0 | 44 |
| **any arm** | **40** | **12** | 0 | 0 | **52 / 886 (5.9%)** |
| rows | 107 | 332 | 327 | 120 | 886 |

What the 51 inferred-arm matches are, judged under the committed rule:

| Under the committed rule the converter's C is | Rows |
|---|---|
| already exact | 6 |
| exact once the trailing filler is cut | 32 |
| different in code | **13** |

## Is the filler flag evidence? Two tests

### Function-start alignment per unit (`unit_census.py`)

Under `-ot`/`-oneatx` every function starts on a 16-byte boundary. So any interior row start
that is not aligned rules a `t` optimisation out for its unit. In the table, "strong" means
three or more interior starts, all aligned; "weak" means one or two, all aligned.

| | `t` strong | `t` weak | not `t` | no evidence |
|---|---|---|---|---|
| UFO2P, default rule | 110 | 84 | 23 | 61 |
| TACP, default rule | 121 | 74 | 26 | 75 |
| UFO2P, `t` rule (approved) | 5 | 1 | 1 | 0 |
| TACP, `t` rule (approved) | 2 | 2 | 0 | 0 |

Not-matched Tier 1 rows by their unit's verdict:

| Unit verdict | Row ends in filler | No filler |
|---|---|---|
| strong | 468 | 191 |
| weak | 69 | 89 |
| not `t` | 16 | 10 |
| no evidence | 1 | 42 |

Alignment is the norm across most of the game. Either `t` optimisation or one-function objects
(each object's `_TEXT` aligned to 16 by the linker) would produce it; this test alone cannot
tell the two apart.

### Matched units under each cell (`control_cells.py`)

The 46 committed units holding the 66 matched functions, each compiled under a different cell:

| Cell | Default/`-o` units, census strong (29) | Census weak (8) | Census not `t` (10) | No evidence (4) | `t`-rule units (15) |
|---|---|---|---|---|---|
| committed rule | 29 | 8 | 10 | 4 | 15 |
| `-4r -oneatx -s -fpi` | **20** | 7 | 8 | 4 | 14 |
| `-4r -ot -s -fpi` | 19 | 6 | 8 | 4 | 4 |
| `-4r -ox -s -fpi` | **29** | 8 | 10 | 4 | 2 |

The functions matched under the default rule in "strong" units keep their bytes under `-ox`,
but lose them under `-oneatx` (9 of 29). Their units were therefore not built with
`-oneatx`. The alignment is the linker's: the original objects held one function each, or a
few. A flag cell has to be proven per function, never assigned per unit.

## Part 2: agents under the inferred cell (3 parallel subagents)

### The sample

`agent_sample.py` (`SEED = 20261102`) drew from default-rule Tier 1 rows that end in filler
and that no converter arm matched:

| Bucket | Pool | Picked |
|---|---|---|
| 64-255 | 195 | 6 |
| 256-1023 | 188 | 5 |
| >=1024 | 64 | 3 |

One general-purpose subagent (Opus 5.5) worked each bucket, with these tools:
- `dump.py`: disassembly to the terminal only;
- `lift.py`: a converter draft;
- `judge_cli.py`: compile and judge under both cells, with `#pragma` and inline asm refused.

Each could write only under `build/spike-011/agents/<bucket>/`, with no git, no `drive`, no
`gate`, and a budget of 25-40 judge runs per function. **The orchestrator re-judged every
file listed;** the table shows those runs.

| Bucket | Function | Exact (inferred) | Exact (committed) | Score | Blocker / key |
|---|---|---|---|---|---|
| 64-255 | ufo2p 0x00034FE0 (64 B) | **yes** | no | 100.0 | explicit struct pointer `p++` next to the counter; declaration order |
| 64-255 | tacp 0x0006BEE0 (80 B) | **yes** | no (exact once the filler is cut) | 100.0 | first try |
| 64-255 | tacp 0x00095800 (80 B) | **yes** | no | 92.0 | 2-D short table, `void`, short parameter |
| 64-255 | tacp 0x00098300 (176 B) | **yes** | no | 98.08 | declaration swap; a separate index temporary for scheduling |
| 64-255 | tacp 0x0001E860 (160 B) | no | no | 98.08 | **every instruction right**; check's leading-jump-table rule refuses 8 bytes of filler between the table and the function |
| 64-255 | ufo2p 0x00051EC0 (176 B) | no | no | 44.71 | **the row is not one function**: an entry jumping into another unit, an epilogue with no prologue (a split question) |
| 256-1023 | ufo2p 0x000483A0 (336 B) | **yes** | no | 98.97 | extern pointer types decided the addressing modes and tail merging |
| 256-1023 | ufo2p 0x0005FBD0 (432 B) | **yes** | no | 100.0 | a struct-returning callee (return pointer in esi); declaration order |
| 256-1023 | tacp 0x000A19D0 (272 B) | no | no | 90.54 | one pair of stack slots swapped; about 10 declaration variants did not move it |
| 256-1023 | tacp 0x0003A120 (400 B) | no | no | 88.58 | a dead value kept in ebp (push/pop) that no C shape reproduced |
| 256-1023 | ufo2p 0x0002DCE0 (272 B) | no | no | 59.5 | stride-6 record addressing and spill choice |
| >=1024 | ufo2p 0x00099050 (1,728 B) | no | no | 82.75 | about 14 spilled locals in other slots; register choices |
| >=1024 | tacp 0x00096130 (2,064 B) | no | no | 50.56 | frame 0xE0 against 0xDC; loop induction registers |
| >=1024 | tacp 0x0009D760 (4,560 B) | no | no | 36.73 | first draft only |

Totals by bucket:

| Bucket | Agent | Exact (inferred) | Time | Subagent tokens |
|---|---|---|---|---|
| 64-255 | b064 | **4/6** | 6.5 min | 110k |
| 256-1023 | b256 | **2/5** | 21 min | 210k |
| >=1024 | b1k | **0/3** (best 82.75) | 29 min | 351k |
| **all** | | **6/14 (43%)** | 57 min | 671k |

Two further checks on these numbers:
- **Committed exact once the filler is cut**, for the 6 matches: only tacp 0x0006BEE0 is. The
  other 5 need `-oneatx` code generation for that C: under the committed rule the same C comes
  out 9-40 bytes short, with different code. The agents wrote their C for the inferred cell, so
  this does not prove that no C matches under the committed rule. But a byte-exact match of up
  to 432 bytes under one cell is strong per-function evidence for it.
- **Against the history.** Opus `drive` sessions have matched 2 of 51 at 64-255 B (3.9% per
  session) and have never been measured at 256 B and up. These subagents ran under different
  conditions: a ready judge for both cells, the converter's draft, a pad for alignment, and
  6-29 minutes with no turn cap. So this is an upper-bound signal from 14 functions, not a
  drive rate.

Process notes:
- The 256-1023 agent saved two disassembly listings to the session scratchpad (outside the
  repo, never staged) against the brief. The orchestrator deleted them; no disassembly file is
  left.
- No agent touched a tracked file (`git status` showed only the spike directory).

## Gate fit (from spike 010 Q5, still open)

None of the 6 agent matches, and none of the converter's filler-row matches, passes the real
`check` as it stands:
- In a unit, the next function is an `INCLUDE_ASM` stub that emits no code, so Watcom adds no
  alignment and our size falls short of the row (spike 010, view 6).
- tacp 0x0001E860 also needs a leading jump table with filler before the function.

`check` accepts nothing here without either:
- **a length rule** that takes trailing Watcom filler up to the next 16-byte boundary at the end
  of our object (byte-safe: `land` keeps the original bytes there, and the whole-EXE SHA-1
  decides); or
- **one-function units**, which would match the original object layout this spike points to.

## Results

### What was learned

- **The converter's ceiling under the right length/alignment rule:** 52/886 (5.9%), almost all
  under 256 B. Most of the gain is alignment, not flags.
- **Agents with the judge and the right cell match well under 1 KB:** 6/11 below 1 KB in one
  sitting each (4/6 at 64-255, 2/5 at 256-1023), against 3.9% per session historically at
  64-255. At 1 KB and up, 0/3 (best 82.75). Stack-slot and register allocation dominate there,
  and only an automatic search over declaration order and types could cover that space.
- **Units probably follow the original one-function objects.** 231 default-rule units have
  every interior start 16-aligned, and the matched functions there keep their bytes under
  `-ox` but not under `-oneatx`.

### What agents asked for (tool ideas, for 07-49/07-50)

- **Declaration-order and extern-type permutation search**, scored with stack offsets masked
  first. This would have closed 0x0005FBD0 in one step and might close 0x000A19D0.
- **A short-type hint.** A slot read only through `movsx word`/`cwde` is a `short`; that was
  worth 16 points on 0x00099050.
- **A partial lift with holes** in place of refusing at the first stack `lea` or x87
  instruction.
- **Idiom detectors:** an inlined boolean helper, and a MIN/MAX macro written out.
- **dump.py upgrades:** show the jump table's case targets, and show which earlier value a
  register holds at a call.

### Signal for the build

1. **Rule first on the length/neighbour question** (07-48 option A, or one-function units). It
   unblocks most filler rows for converter and agents alike, and with its 32 alignment-only
   rows it is worth more than any flag change.
2. **Propose `-oneatx` per function**, only where an exact match under that cell exists (13
   converter rows and 5 agent rows here), through the existing D-12 queue.
3. **Run the tail with agents that have this harness:** a judge for both cells and the
   converter's draft. That is worth a real `drive` comparison on the same rows.
4. **For 1 KB and up, build the declaration-order and type search** before spending agent nights.

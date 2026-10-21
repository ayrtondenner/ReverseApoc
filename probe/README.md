# Codegen probe

`cg_basic.c` is a small C89 source compiled with every swept Watcom version (10.5, 10.6, 11.0)
and a fixed list of flag sets. `tools/reverseapoc/probe.py` counts byte-level idioms in each
object, so we know which idiom each version and flag set emits before the same idioms are counted
in the game's non-library code (CID-03, D-10). Research found that mosura's register claims do
not reproduce with a probe of our own (04-RESEARCH Pitfall 9), so every idiom is calibrated here
rather than taken from a published table.

## Clean-room note

The probe is written in-house for ReverseApoc. The constructs come from mosura's documented list
(byte compare return, counted loop, switch order) plus the constructs the flag scans need. No
file from mosura or any other project is copied: mosura's licence is unverified.

## Constructs

| Function | Construct | What it discriminates | Research |
|---|---|---|---|
| `pr_eq5` | `return c == 5;` on an `unsigned char` | `setcc al; and eax,0FFh` (-4/-5, and 11.0 only at -4) vs `setcc al; movzx eax,al` (-3) vs a branch (11.0 at -5) | Pattern 6, row 1 |
| `pr_sum` | `for (i = 0; i < n; i++) s += a[i];` | rotated loop (10.x: `jmp` to a bottom test, `jl` back) vs top-tested loop (11.0: `cmp; jge` exit, `jmp` back) | Pattern 6, row 2 |
| `pr_switch` | `switch` on 1, 2, 3, 10 with a default | the order of the compare chain (ascending vs descending), mostly under `-ox` | Pattern 6, row 4 |
| `pr_copy` | `*dst = *src` on a five-dword struct | unrolled `movsd` (-5) vs `mov ecx,5; rep movsd` (-4) | Pattern 6, row 3 |
| `pr_div10` | `x / 10` | constant division (reciprocal multiply vs `idiv`); kept for the `-o*` scans | Pattern 6, flag matrix |
| `pr_fexpr` | `a * b + c` on doubles | inline x87; `-fpi` asks for `emu387`, `-fpi87` for `noemu387` (default-library COMENT) | Pattern 6, rows 5-7 |
| `pr_call` | calls `pr_div10` and `pr_eq5` | a stack-check prologue (`__CHK` calls without `-s`, none with `-s`) | Pattern 6, flag matrix |

Loop and switch counts are byte-level matches over raw code and are not decisive on their own
(research A7 and Pattern 6): a byte pattern can also hit data or the middle of an instruction.

## Calibration (host, 2026-10-21)

Measured natively on the Windows host with `probe.calibrate()` (wcc386 through `reverseapoc cc`'s
wrapper: `-zq -zld -bt=dos` plus the flags shown). Counts summed over the probe's CODE segment;
`and` = setcc_and, `movzx` = setcc_movzx, `movsd` = movsd_unrolled, `rep` = rep_movsd_small,
`rot` / `top` = loop_rotated / loop_top_tested, `sw_up` / `sw_down` = switch_ascending /
switch_descending, `__CHK` = self-relative fixups to `__CHK`. 10.5 is skipped until plan 04-11
reinstalls its BINW compiler. No two versions produced the same normalized object under any flag
set, so there are no ties between 10.6 and 11.0.

| version | flags | and | movzx | movsd | rep | rot | top | sw_up | sw_down | `__CHK` | default libraries |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10.6 | `-3r -s` | 0 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-4r -s` | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 7 | math387r, emu387 |
| 10.6 | `-4r -s -ox` | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -ox` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -oneatx` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -os` | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -fpi87` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, noemu387 |
| 10.6 | `-5s -s` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387s, emu387 |
| 11.0 | `-3r -s` | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | math387r, emu387 |
| 11.0 | `-4r -s` | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s` | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r` | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 7 | math387r, emu387 |
| 11.0 | `-4r -s -ox` | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -ox` | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -oneatx` | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -os` | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -fpi87` | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | math387r, noemu387 |
| 11.0 | `-5s -s` | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | math387s, emu387 |

What the table says, and where it differs from 04-RESEARCH Pattern 6:

- Byte compare: `movzx` at `-3r` for both versions; `and` at `-4r`/`-5r` for 10.6 and at `-4r`
  for 11.0; neither form for 11.0 at `-5r` (a branch). Also measured: 10.6 at `-5r -s -os` emits
  `movzx`, so `movzx` alone does not prove `-3`.
- Struct copy: five unrolled `movsd` at `-5`, none at `-3`/`-4`. The research row "`-4r` gives
  `mov ecx,5; rep movsd`" holds as mnemonics, but the two instructions are not adjacent in the
  probe (`mov ecx,5` sits 9 bytes before `rep movsd`), so the adjacent `rep_movsd_small`
  encoding counts 0 in every cell. A game-code count of 0 for it does not rule out `-4`.
- Loops: rotated in 10.6 and top-tested in 11.0 under every flag set except `-oneatx`, where
  neither shape is found (as the research noted).
- Switch: an ascending chain in pr_switch for most cells; the one descending hit (11.0
  `-5r -s -ox`) is byte-level noise that starts in pr_eq5, which is why switch counts are not
  decisive.
- Stack checks: 7 `__CHK` calls without `-s` (one per function), none with `-s`.
- Libraries: `-fpi` requests emu387 and `-fpi87` noemu387; `-5s` requests math387s. No cell
  requests a CLIB library (clib3r or clib3s), so the research's "`-5s` gives clib3s" does not
  show here. The probe calls no CLIB function, which may be why; this was not tested.

## Running the calibration

`uv run reverseapoc probe calibrate` (the CLI verb arrives with plan 04-10). Until then the
calibration runs through `tests/test_probe_real.py` or `probe.calibrate()`. Objects go under
`build/probe/<version>/<flags>/` (gitignored). Output holds counts, library names and SHA-1s,
never object bytes.

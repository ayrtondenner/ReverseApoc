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

## Running the calibration

`uv run reverseapoc probe calibrate` (the CLI verb arrives with plan 04-10). Until then the
calibration runs through `tests/test_probe_real.py` or `probe.calibrate()`. Objects go under
`build/probe/<version>/<flags>/` (gitignored). Output holds counts, library names and SHA-1s,
never object bytes.

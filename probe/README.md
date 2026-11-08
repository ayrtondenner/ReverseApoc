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
| `pr_switch` | `switch` on 1, 2, 3, 10 with a default | the order of the compare chain (ascending vs descending), mostly under `-ox`; measured ascending on both versions (see the calibration) | Pattern 6, row 4 |
| `pr_copy` | `*dst = *src` on a five-dword struct | unrolled `movsd` (-5) vs `mov ecx,5`, two register moves, `rep movsd` (-3/-4) | Pattern 6, row 3 |
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

Re-run on 2026-10-21 after review fix round 1, which corrected the switch chain counter and
changed `rep` to the measured struct-copy shape (see the 04-08 SUMMARY). Only the `rep`, `sw_up`
and `sw_down` columns changed: `rep` now hits at `-3r`, `-4r` and `-4r -ox`, and every 11.0
switch cell now reads like 10.6.

| version | flags | and | movzx | movsd | rep | rot | top | sw_up | sw_down | `__CHK` | default libraries |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10.6 | `-3r -s` | 0 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-4r -s` | 1 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 7 | math387r, emu387 |
| 10.6 | `-4r -s -ox` | 1 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -ox` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -oneatx` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -os` | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -fpi87` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, noemu387 |
| 10.6 | `-5s -s` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387s, emu387 |
| 11.0 | `-3r -s` | 0 | 1 | 0 | 1 | 0 | 1 | 1 | 0 | 0 | math387r, emu387 |
| 11.0 | `-4r -s` | 1 | 0 | 0 | 1 | 0 | 1 | 1 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s` | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r` | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 7 | math387r, emu387 |
| 11.0 | `-4r -s -ox` | 1 | 0 | 0 | 1 | 0 | 1 | 1 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -ox` | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -oneatx` | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -os` | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -fpi87` | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | math387r, noemu387 |
| 11.0 | `-5s -s` | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | math387s, emu387 |

What the table says, and where it differs from 04-RESEARCH Pattern 6:

- Byte compare: `movzx` at `-3r` for both versions; `and` at `-4r`/`-5r` for 10.6 and at `-4r`
  for 11.0; neither form for 11.0 at `-5r` (a branch). Also measured: 10.6 at `-5r -s -os` emits
  `movzx`, so `movzx` alone does not prove `-3`.
- Struct copy: five unrolled `movsd` at `-5`, none at `-3`/`-4`. At `-3r` and `-4r` both versions
  emit `mov ecx,5`, then two register moves (loading edi and esi), then `rep movsd`, so the
  research row "`-4r` gives `mov ecx,5; rep movsd`" holds as mnemonics. `rep_movsd_small` counts
  that measured shape (up to four register moves between, review fix round 1), and it is 0 in
  every `-5` cell, so `rep` vs `movsd` separates `-3`/`-4` from `-5`. The plan's adjacent
  encoding counted 0 in every cell, so the research's game-code count of 0 for it never ruled
  out `-4`; plan 04-10 recounts it.
- Loops: rotated in 10.6 and top-tested in 11.0 under every flag set except `-oneatx`, where
  neither shape is found (as the research noted).
- Switch: one ascending chain and no descending chain in every cell except `-oneatx` (none), on
  both versions, so switch order does not separate 10.6 from 11.0 on the probe. The first table
  showed 11.0 zeros and one descending hit (11.0 `-5r -s -ox`). Those came from counter defects,
  not from the codegen and not from byte noise. A compare that turned the direction dropped the
  real chain: pr_eq5's `cmp al,5; jne` did so in the 11.0 `-5` cells with `-s`, and pr_switch's
  own first compare did so at 11.0 `-4r -s -ox`. A compare in another function could also join a
  chain: pr_eq5's compare and two of pr_switch's formed the descending hit. Both defects were fixed in review round 1. The research's different 11.0 `-ox`
  jcc forms show only in the chain's start: pr_switch's first compare turns the direction, so the
  ascending chain starts at its second compare. The order counter does not separate that shape.
- Stack checks: 7 `__CHK` calls without `-s` (one per function), none with `-s`.
- Libraries: `-fpi` requests emu387 and `-fpi87` noemu387; `-5s` requests math387s. No cell
  requests a CLIB library (clib3r or clib3s), so the research's "`-5s` gives clib3s" does not
  show here. The probe calls no CLIB function, which may be why; this was not tested.

## Stack slots (Phase 7.1)

`cg_slots.c` measures the frame of wcc386 10.6 under `-4r -s -fpi` and `-4r -oneatx -s -fpi`, and `tools/reverseapoc/slots.py` is the model it calibrates (D-02). No game code and no matched row is an input. `tests/test_slots_real.py` compiles it through `batch.compile_batch` and reads each local's offset from a marker constant.

It stays out of `probe.PROBE_SOURCES`, and neither cell joins `probe.FLAG_SETS`: `calibrate` sums over both, so adding either would change the Phase 4 table above.

| Functions | Construct | What they measure |
|---|---|---|
| `pr_slot_same_size`, `pr_slot_bytes`, `pr_slot_shorts` | ties of one size, each with a `_rev` twin | M2: the first declared sits highest |
| `pr_slot_mixed`, `pr_slot_array`, `pr_slot_struct`, `pr_slot_odd`, each with a `_rev` twin | distinct sizes | M1 and M3: the largest lowest, by total size, each padded to 4, whatever the declaration order |
| `pr_slot_unaligned` | `char[12]`, `double`, `int` | nothing aligns past 4: the double sits at 0xC |
| `pr_slot_flat`, `pr_slot_scope`, `pr_slot_scope_pairs` | three ints flat and in nested blocks | M4: an earlier block sits lower, the first declared of a block highest, and the frame stays 0xC |
| `pr_slot_siblings`, `pr_slot_block_order` | sibling blocks | M4: siblings share nothing, and the key is the place of the block in the source, not its depth |
| `pr_slot_unused` | locals nothing uses | they take no slot, an array included |
| `pr_slot_volatile`, `_volatile_rev`, `_volatile_init` | a volatile beside ints, and one with only an initializer | a volatile takes a slot with no address taken, and M2 places it |
| `pr_slot_float_taken`, `pr_slot_float_array`, `pr_slot_double_int` | floats and doubles in memory, or in no tie | M2 holds for an address-taken float, and M1 for a float or a double with no tie |
| `pr_float_ints`, `pr_float_tie`, `_tie_rev` | a float with no address taken, in a tie | it leaves M2, yet declarations still move it, so the search keeps its plain moves |
| `pr_double_called`, `pr_double_stored` | one declaration list, two uses of a double | the ints beside it swap, so no rule on declarations places them |
| `pr_twin_abc`, `_bca`, `pr_twin_ints_double`, `_double_ints`, `pr_thin_ours`, `_theirs` | twins for the search | on a real slot map it computes the first pair and keeps its plain moves for the others: a double beside the tie, and a map that cannot place `c` |
| `pr_tie_*` | ties the model refuses | where M2 and M4 stop: each is proven to leave declaration order, and M1 and M3 still hold |
| `pr_arr_*` | arrays of one total size, alone and beside scalars | which side of the rule each lies on, and the frames the model refuses though they hold: the line runs through no count |
| `pr_spill_decl`, `_decl_rev`, `_scoped` | eight values live across calls | M5: declaration and scope leave the code identical |
| `pr_spill_assign`, `_use`, `_type`, `_loop`, `_loop_late` | one change each | M5: assignment order, use order, type and loop weight change the code |
| `pr_spill_short`, `_short_rev` | shorts spilled beside a short in memory | the exception to M5: declarations move them under `-oneatx` |
| `pr_spill_memory`, `pr_spill_small` | spills beside memory locals | a spill sorts by size: above an int or an array, below a short |

What it measured, and where that differs from the preview in 07.1-RESEARCH:

- **M1 and M3 always held,** ties or not, in both cells.
- **M2 is narrower than the preview.** A tie follows declaration order only when the whole frame has that one size, of 1, 2 or 4 bytes, or, for ints, across blocks. `int[2]` ties are not reversed even alone (`pr_tie_three`); a pair of them flips beside one `int` (`pr_tie_pair`); plain ints flip beside larger locals (`pr_tie_small`); `int a; int b; short c; short d;` reverses the ints and not the shorts (`pr_tie_sizes`). Three or more multi-element arrays leave M2 even alone in a frame of one size: from first declared to last, three `char[4]`, `unsigned char[4]` or `short[2]` sit at 4, 8, 0, four `char[4]` at 4, 0xC, 8, 0, and three `char[2]` at 0, 8, 4 (`pr_arr_char4_x3`, `pr_arr_uchar4_x3`, `pr_arr_short2_x3`, `pr_arr_char4_x4`, `pr_arr_char2_x3`). Beside other locals the array count is not the line. At size 2 an array beside plain locals often leaves M2, one array is enough, and whether it does turns on the count and the place: `char a[2]; char b[2]; short c;` sits at 4, 8, 0 (`pr_arr_two_one_small`, `pr_arr_one_two_small`), where a frame of four holds (`pr_arr_two_two_small`). At size 4, up to two arrays held beside up to nine ints in one block, but two arrays beside a later block leave M4 (`pr_arr_two_block`, `pr_arr_short2_block`, `pr_arr_int_two_block`), and three arrays leave M2 behind an `int` and hold before one (`pr_arr_int_three`, `pr_arr_three_int`). So in a frame of one size `order_is_known` refuses more than the compiler's line: an array of 2 bytes beside a plain local, two arrays across blocks, and three arrays anywhere, some of which hold. A sweep of 260 frames in both cells left no frame it calls known and places wrongly, and frames past that sweep are not measured.  A local outside a tie changes it (`pr_tie_three_int`), so these orders are not a table by count. Common sort algorithms, tried against the counts up to 13, did not reproduce them, and `slots.order_is_known` refuses them.
- **M4's key is the block's place in the source,** not its depth, and it holds for ints only: chars and shorts do not follow their blocks (`pr_tie_scope_shorts`).
- **M5 has one exception** (`pr_spill_short`), and spill slots do not always start at 0: they start above the memory locals of 4 bytes or more.
- `-4r -s` folds byte-identical functions onto one offset and merges identical tails across functions, so a reader of this object must take a function's end from the next greater public offset, and a shape needs its own tail to keep its markers.

## Signed divide by a power of two (quick task 261107-qkb)

`cg_divide.c` measures the form wcc386 10.6 gives `x / 2^n` for a signed `int`, which `tools/reverseapoc/lift.py` turns back into that divide. No game code and no matched row is an input. `tests/test_lift_divide_real.py` compiles it through `batch.compile_batch` under the `*` rule of `config/cflags.txt` (`-4r -s -fpi`), lifts each function's bytes from a stub row, and compiles the draft back to the same bytes. It stays out of `probe.PROBE_SOURCES` and `probe.FLAG_SETS`, so the Phase 4 table above does not change.

| Function | Construct | Form it compiled to |
|---|---|---|
| `pr_div2` | `x / 2` | `push edx; mov edx, eax; sar edx, 31; sub eax, edx; sar eax, 1; pop edx; ret` |
| `pr_div4` | `x / 4` | `push edx; mov edx, eax; sar edx, 31; shl edx, 2; sbb eax, edx; sar eax, 2; pop edx; ret` |
| `pr_div16` | `x / 16` | `push edx; mov edx, eax; sar edx, 31; shl edx, 4; sbb eax, edx; sar eax, 4; pop edx; ret` |
| `pr_div8_load` | `*p / 8` | `push edx; mov edx, eax; mov eax, [eax]; mov edx, [edx]; sar edx, 31; shl edx, 3; sbb eax, edx; sar eax, 3; pop edx; ret`: the sign comes from a second load, not a copy |
| `pr_div2_second` | `a + b / 2` | `push ebx; mov ebx, eax; mov eax, edx; sar edx, 31; sub eax, edx; sar eax, 1; add eax, ebx; pop ebx; ret` |

`cdq; xor eax, edx` (abs) is not in the probe, and the lifter still refuses it.

## Lifter round trip (quick 261107-qkd)

`cg_lift.c` measures the C forms `tools/reverseapoc/lift.py` writes for string moves and x87 forms, each function written in the shape the lifter writes, with register-named parameters. No game code and no matched row is an input. `tests/test_lift_probe_real.py` compiles it through `batch.compile_batch` under `-4r -s -fpi` ("plain") and `-4r -oneatx -s -fpi` ("oneatx", the search cell), lifts each function's bytes from a stub row, and compiles the draft under the same cell back to the same bytes. No function calls or reads a global, since the stub row has no fixups. It stays out of `probe.PROBE_SOURCES` and `probe.FLAG_SETS`, so the Phase 4 table above does not change.

| Function | C form | Bytes, plain and oneatx alike |
|---|---|---|
| `pr_lift_copy_<S>`, S = 3, 5-12, 16-19 | `*(struct copy_S *)r_eax = *(struct copy_S *)r_edx;` with `struct copy_S { char b[S]; };` | `push esi; push edi; mov edi, eax; mov esi, edx`, then S / 4 `movsd`, a `movsw` when S % 4 >= 2 and a `movsb` when S is odd, then `pop edi; pop esi; ret` |
| `pr_lift_copy_20`, `_21`, `_46` | the same, 20, 21 and 46 bytes | `push ecx` first, `mov ecx, S / 4` ... `rep movsd`, then the same tail, `pop ecx` last |
| `pr_lift_copy_24` | eax to edx, then `return *(int *)r_edx;` | the rep form, then the load: a rep with no tail ends the same way whatever the registers, and plain jumps into the 20-byte copy's `rep movsd` without it |

| Function | C form | Bytes under oneatx (plain: `call strlen_` or `call memcpy_`) |
|---|---|---|
| `pr_lift_strlen` | `return strlen((char *)r_eax);` with `#include <string.h>` | `push ecx; push edi; mov edi, eax; sub ecx, ecx; dec ecx; xor eax, eax; repne scasb; not ecx; dec ecx; mov eax, ecx; pop edi; pop ecx; ret` |
| `pr_lift_strlen_store` | `*(unsigned *)r_edx = strlen((char *)r_eax); return 0;` | the same template, then `mov [edx], ecx` |
| `pr_lift_memcpy` | `memcpy((void *)r_eax, (void *)r_edx, r_ebx); return r_eax;` | `push ecx; push esi; push edi; push ebp; mov ebp, eax; mov ecx, ebx; mov esi, edx; mov edi, eax; push edi; mov eax, ecx; shr ecx, 2; repne movsd (F2 A5); mov cl, al; and cl, 3; repne movsb; pop edi; mov eax, ebp; pop ebp; pop edi; pop esi; pop ecx; ret` |

The inline forms come only under oneatx: string.h's intrinsic pragma needs `-oi`, which `-ox` and `-oneatx` hold. A stub row has no caller to say its eax goes unread, so what a void function leaves in eax reads back as returned: the strlen template leaves 0, so the store case returns 0, and a memcpy leaves its count, so the memcpy case returns its destination. A game row gets `void` from the census when no caller reads eax. Inline strcat (`push edi; sub ecx, ecx; dec ecx; mov al, 0; repne scasb; dec edi`, then a copy loop over three blocks) is not in the probe, and the lifter still refuses it as `op: repne scasb`.

A char struct gives the same bytes as an int struct of that size. Up to four dwords are unrolled and five or more take `rep movsd`; S = 1, 2 and 4 copy through a register, with no string op, and the lifter refuses a lone `movsd`, `movsw` or `movsb`. Plain `-4r -s` merges identical tails across the functions of one file, so the test refuses a function with a jump outside itself and names it.

## Running the calibration

`uv run reverseapoc probe calibrate [--output build/probe/calibration.json]` (plan 04-10); the
calibration also runs through `tests/test_probe_real.py` or `probe.calibrate()`. Since plan 04-11
reinstalled 10.5 with its decoded compiler, the table covers 10.5 as well: 10.5 and 10.6 give
byte-identical objects in all ten flag sets. Objects go under
`build/probe/<version>/<flags>/` (gitignored). Output holds counts, library names and SHA-1s,
never object bytes. If the hash gate (D-13) refuses any requested version, the verb prints the
table, exits 1 and writes no calibration; pass `--versions` to calibrate only the versions you
have installed.

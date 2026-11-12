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

## Where the figures come from

Every figure in this file comes from a probe source in this directory, compiled the way the test
its section names compiles it. Claims quoted from 04-RESEARCH or 07.1-RESEARCH say so where they
stand. A figure measured outside `probe/`, on scratch clean-room C, by a researcher, planner,
reviewer or sweep script, carries a parenthesis that opens with `preview:` and names where it was
recorded, and no test here reproduces it. Some figures are read off the compiled probe, because
the tests round-trip those functions or check their order but do not assert their text. These
were re-read on 2026-11-09 in quick 261109-gzz, in both cells where the test uses both: the
divide table, under `-4r -s -fpi` only as its test compiles it; the lifter's tables and the plain
calls in their headers; the lifter's goto form; the orders given for `pr_tie_small` and
`pr_tie_sizes`; and the fold and the merged tails of `-4r -s`, which the plain `cg_slots.c`
object shows.

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
| `pr_line_a_*`, `_b_*`, `_c_*`, `_d_*`, `_k_*` | frames past the 07.1 sweep (quick 261112-fdx), some with their use reversed (`_late`) or the array in a call of its own (`_split`) | each tests one of four lines fixed before it was measured, or (`_k_`) the side the model already calls known |
| `pr_spill_decl`, `_decl_rev`, `_scoped` | eight values live across calls | M5: declaration and scope leave the code identical |
| `pr_spill_assign`, `_use`, `_type`, `_loop`, `_loop_late` | one change each | M5: assignment order, use order, type and loop weight change the code |
| `pr_spill_short`, `_short_rev` | shorts spilled beside a short in memory | the exception to M5: declarations move them under `-oneatx` |
| `pr_spill_memory`, `pr_spill_small` | spills beside memory locals | a spill sorts by size: above an int or an array, below a short |

What it measured, and where that differs from the preview in 07.1-RESEARCH:

- **M1 and M3 always held,** ties or not, in both cells.
- **M2 is narrower than the preview.** A tie follows declaration order only when the whole frame has that one size, of 1, 2 or 4 bytes, or, for ints, across blocks. `int[2]` ties are not reversed even alone (`pr_tie_three`); a pair of them flips beside one `int` (`pr_tie_pair`); plain ints flip beside larger locals, and so does the `int[2]` pair beside them (`pr_tie_small`); `int a; int b; short c; short d;` reverses the ints and not the shorts (`pr_tie_sizes`). Three or more multi-element arrays leave M2 even alone in a frame of one size: from first declared to last, three `char[4]`, `unsigned char[4]` or `short[2]` sit at 4, 8, 0, four `char[4]` at 4, 0xC, 8, 0, and three `char[2]` at 0, 8, 4 (`pr_arr_char4_x3`, `pr_arr_uchar4_x3`, `pr_arr_short2_x3`, `pr_arr_char4_x4`, `pr_arr_char2_x3`). Beside other locals the array count is not the line. At size 2 an array beside plain locals often leaves M2, one array is enough, and whether it does turns on the count and the place: `char a[2]; char b[2]; short c;` sits at 4, 8, 0 (`pr_arr_two_one_small`, `pr_arr_one_two_small`), where a frame of four holds (`pr_arr_two_two_small`). At size 4, up to two arrays held beside up to nine ints in one block (preview: 07.1-07's review and its sweep, recorded in 07.1-07-SUMMARY.md; the probe holds two arrays beside up to two ints and one beside up to three), but two arrays beside a later block leave M4 (`pr_arr_two_block`, `pr_arr_short2_block`, `pr_arr_int_two_block`), and three arrays leave M2 behind an `int` and hold before one (`pr_arr_int_three`, `pr_arr_three_int`). Past the 07.1 sweep, 07.2-14 measured in both cells: a `char[4]` beside a `short[2]` keeps M2 (`pr_arr_c4_s2`), two `char[4]` beside a `short[2]` sit at 4, 8, 0 as three `char[4]` do (`pr_arr_c4x2_s2`), a `char[4]` and an `int` beside a `char[2]` hold though the model refuses a frame of two sizes (`pr_arr_c4_c2_int`), and three `int[1]`, the lifter's form for a 4-byte address-taken slot, keep M2 (`pr_arr_int1_x3`); each with a `_rev` twin, and none moved the model. Quick 261112-fdx fixed four lines before measuring their frames in both cells, and drew three. Line A: one 2-byte array declared first keeps M2 beside 1 to 11 shorts (`pr_line_a_c2_h` to `pr_line_a_c2_h11`, `_uc2_h3`, `_c2_mixed`, `_c2_h3_late`, `_c2_h3_split`, and `pr_arr_one_three_small`). Line B: two 4-byte arrays declared first, then 1 to 3 ints in the top block, keep M2 and M4 beside up to two later blocks of 1 to 5 ints (`pr_line_b_c4x2_i_blk`, `_i3_blk`, `_i_blk5`, `_i_blk_blk`, `_c4_s2_i_blk`, `_i_blk_late`). Line C: three or four 4-byte arrays declared first, then 1 or 2 ints, keep M2 in one block (`pr_line_c_c4x2_s2_i`, `_c4x3_i2`, `_c4x4_i`, `_c4x3_i_late`, and `pr_arr_three_int`). Line D, a 4-byte array and an int beside one 2-byte local, broke: `char a[4]; int b; char c[2];` and `int a; char b[4]; short c;` sit at 0, 4, 8 (`pr_line_d_c4_i_c2`, `pr_line_d_i_c4_h`), where `pr_line_d_c4_i_h`, `_h_i_c4`, `_c4_c2_i_late` and the control `pr_line_d_i2_h` hold. The four `pr_line_k_` frames the model already called known, past the sweep's counts, all sit where it puts them. So in a frame of one size `order_is_known` still refuses more than the compiler's line: two 2-byte arrays beside a plain local, an array not declared first beside plain ones, two arrays across blocks with no int after them in the top block, and three arrays with none after them, some of which hold. A sweep of 260 frames in both cells left no frame it calls known and places wrongly, and past that sweep only 07.2-14's and 261112-fdx's frames are measured (preview: build/gate/07.1-evidence/07-verify-review.py, which is not tracked; its counts are in 07.1-07-SUMMARY.md: 260 frames, 161 known and held, 58 refused and left, 41 refused and held, 0 known and wrong). A local outside a tie changes it (`pr_tie_three_int`), so these orders are not a table by count. Common sort algorithms, tried against the counts up to 13, did not reproduce them (preview: 07.1-02's scratch simulations of a shell sort over every gap subset, a heap sort and a Hoare partition, recorded in 07.1-02-SUMMARY.md; no script for them is in the repo), and `slots.order_is_known` refuses them.
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
| `pr_lift_copy_24` | eax to edx, then `return *(int *)r_edx;` | the rep form, then the load: a rep with no tail ends the same way whatever the registers, and plain jumps into the 20-byte copy's `rep movsd` without it (preview: quick 261107-qkd, on an earlier cg_lift.c; the current probe avoids that shape) |

| Function | C form | Bytes under oneatx (plain: `jmp strlen_` in `pr_lift_strlen`, `call strlen_` in `pr_lift_strlen_store`, `call memcpy_` in `pr_lift_memcpy`) |
|---|---|---|
| `pr_lift_strlen` | `return strlen((char *)r_eax);` with `#include <string.h>` | `push ecx; push edi; mov edi, eax; sub ecx, ecx; dec ecx; xor eax, eax; repne scasb; not ecx; dec ecx; mov eax, ecx; pop edi; pop ecx; ret` |
| `pr_lift_strlen_store` | `*(unsigned *)r_edx = strlen((char *)r_eax); return 0;` | the same template up to `not ecx; dec ecx`, then `xor eax, eax; mov [edx], ecx; pop edi; pop ecx; ret` |
| `pr_lift_memcpy` | `memcpy((void *)r_eax, (void *)r_edx, r_ebx); return r_eax;` | `push ecx; push esi; push edi; push ebp; mov ebp, eax; mov ecx, ebx; mov esi, edx; mov edi, eax; push edi; mov eax, ecx; shr ecx, 2; repne movsd (F2 A5); mov cl, al; and cl, 3; repne movsb; pop edi; mov eax, ebp; pop ebp; pop edi; pop esi; pop ecx; ret` |

The inline forms come only under oneatx: string.h's intrinsic pragma needs `-oi`, which `-ox` and `-oneatx` hold (preview: the planning of quick 261107-qkd; the probe compiles only plain and oneatx, so it shows the split, not the flag behind it). A stub row has no caller to say its eax goes unread, so what a void function leaves in eax reads back as returned: the strlen template leaves 0, so the store case returns 0, and a memcpy leaves its count, so the memcpy case returns its destination. A game row gets `void` from the census when no caller reads eax. Inline strcat (`push edi; sub ecx, ecx; dec ecx; mov al, 0; repne scasb; dec edi`, then a copy loop over three blocks) is not in the probe (preview: the planning of quick 261107-qkd, on scratch C under oneatx), and the lifter still refuses it as `op: repne scasb`.

| Function | C form, with `#include <math.h>` | Bytes |
|---|---|---|
| `pr_lift_sqrt` | `*(double *)r_eax = sqrt(*(double *)r_edx);` | oneatx: `push ebx; mov ebx, eax; fld qword ptr [edx]; fsqrt; fstp qword ptr [ebx]; pop ebx; ret`; plain calls `IF@DSQRT` |
| `pr_lift_log` | the same with `log` | oneatx: `fldln2; fxch st(1); fyl2x` in place of `fsqrt`; plain calls `IF@DLOG` |
| `pr_lift_fabs` | the same with `fabs` | both cells: `fabs` in place of `fsqrt` |
| `pr_lift_one_minus` | `*(double *)r_eax = 1.0 - *(double *)r_edx;` | both: `fld qword ptr [edx]; fld1; fsubrp st(1); fstp qword ptr [eax]; ret` |
| `pr_lift_plus_one` | `*(double *)r_edx = *(double *)r_eax + 1.0;` | both: `fld qword ptr [eax]; fld1; faddp st(1); fstp qword ptr [edx]; ret` |
| `pr_lift_below_zero` | `return *(double *)r_eax < 0.0;` | both: `fldz; fcomp qword ptr [eax]; fnstsw ax; sahf; jbe L; mov eax, 1; ret; L: xor eax, eax; ret` |

math.h's intrinsic pragma inlines sqrt and log only with `-om`, which `-ox` and `-oneatx` hold (preview: the planning of quick 261107-qkd; the probe compiles only plain and oneatx, so it shows the split, not the flag behind it). A bare prototype with no header compiles sqrt, log, fabs, strlen and memcpy to calls in both cells, with the double argument pushed (preview: the planning of quick 261107-qkd, on scratch C; the probe includes both headers), so every math form the lifter writes declares itself through `#include <math.h>`. The lifter writes `fldln2` as `log(2.0)`, the C89 value of ln 2, and lifts `fyl2x` only over it. `1.0 - x` and `x + 1.0` give `fld1` on doubles and floats alike (preview: the floats half comes from the planning of quick 261107-qkd; the probe holds doubles only); `x + 0.0`, `0.0 - x` and `x * 0.0` fold away and give no `fldz` (preview: the planning of quick 261107-qkd, on scratch C). The lifter's goto form of the compare, which it drafts from the stub row as `if (0.0 <= (*(double *)((char *)r_eax))) goto L100F; return 1; L100F:; return 0;`, compiles to the same bytes as `< 0.0`. A free `fxch` came only from doubles passed on the stack under oneatx, which the lifter reads as `int r_pN` parameters (preview: the planning of quick 261107-qkd, on scratch C), so the log case carries the round trip's fxch and the unit tests cover the other registers. math.h declares `y0`, `y1`, `yn`, `j0`, `j1` and `jn` (preview: the planning of quick 261107-qkd, where a probe function named y1 failed to compile), so no probe function takes those names.

A char struct gives the same bytes as an int struct of that size (preview: the planning of quick 261107-qkd, where a 20-byte char struct and a 5-int struct folded onto one offset). Up to four dwords are unrolled and five or more take `rep movsd`; S = 1, 2 and 4 copy through a register, with no string op (preview: the planning of quick 261107-qkd, on scratch C at S = 1, 2 and 4; the probe holds no copy of 1, 2 or 4 bytes), and the lifter refuses a lone `movsd`, `movsw` or `movsb`. Plain `-4r -s` merges identical tails across the functions of one file, as the plain `cg_slots.c` object shows; in the plain `cg_lift.c` object only `pr_lift_strlen` leaves itself, by its `jmp strlen_`, and it round-trips under oneatx only. So the test refuses a function with a jump outside itself and names it.

The `pr_lift_taken_*` functions (07.2-14) take the address of three 4-byte stack slots and store each address through `r_eax`. The lifter declares such a slot `int s_X[1]` and reaches inside one through `(char *)s_X + k`; `pr_lift_taken_x3` and `_byte` (an `int[1]` original, the second with a byte store inside a slot) round-trip in both cells, and `pr_lift_taken_chars` (a `char[4]` original with byte stores) in plain only, because `-oneatx` builds its byte constants in one register, a form the lifter writes as a mask that does not compile back.

## Running the calibration

`uv run reverseapoc probe calibrate [--output build/probe/calibration.json]` (plan 04-10); the
calibration also runs through `tests/test_probe_real.py` or `probe.calibrate()`. Since plan 04-11
reinstalled 10.5 with its decoded compiler, the table covers 10.5 as well: 10.5 and 10.6 give
byte-identical objects in all ten flag sets. Objects go under
`build/probe/<version>/<flags>/` (gitignored). Output holds counts, library names and SHA-1s,
never object bytes. If the hash gate (D-13) refuses any requested version, the verb prints the
table, exits 1 and writes no calibration; pass `--versions` to calibrate only the versions you
have installed.

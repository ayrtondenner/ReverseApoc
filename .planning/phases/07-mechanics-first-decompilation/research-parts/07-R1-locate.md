# Phase 7 research, slice 1 of 3: locating the mechanics

**Researched:** 2026-10-26
**Scope:** DEC-01 (all of it), DEC-05 (the data side: what the coverage view reads), the roadmap spike, owner rulings D-01..D-05
**Confidence:** HIGH for the measurements (scratch scripts run this session on the real EXEs), MEDIUM for the item-to-entry mapping (drafts the spike must confirm), LOW where tagged `[ASSUMED]`

All numbers below come from throwaway scripts in the session scratchpad, run with `uv run python -I` against `orig/` and the Steam `cd.iso`, read-only. This file holds addresses, counts, names and short identifying strings only: no disassembly, no table contents.

---

## #997 FINDING (report to owner)

**This is a strong lead, not the answer. Matched code backs none of it** (`config/ufo2p/status.csv` and `config/tacp/status.csv` list none of these functions as matched).

1. **What paces game time: the BIOS tick, not the PIT.** [VERIFIED: capstone scan of both EXEs this session]
   - UFO2P `func_00011430` (unit `u_00011430`) calls the runtime `int386_` with interrupt `0x1A`. That is BIOS INT 1Ah, the 18.2065 Hz system tick (1,193,182 / 65,536). It also handles the midnight rollover. It has **28 direct callers**.
   - TACP has the same pattern: `func_00011500` and `func_000116B0` call `int386_` with `0x1A`. `func_00011500` has 35 direct callers.
   - No game code in either EXE reads the BIOS tick word at linear `0x46C` directly. Searches for `[0x46c]`, segment-override reads and port `0x3DA` (vertical retrace) found none.
2. **The INT 8 / PIT code is the sound library's timer, not the game clock.** [VERIFIED: scan; library identity ASSUMED]
   - The only PIT programming (mode byte to port `0x43`, divisor to port `0x40`) and the only INT 8 installs (DPMI `0204h`/`0205h` and DOS `3508h`/`2508h`) are in UFO2P `0xC8E41..0xC90F3` and TACP `0xCC151..0xCC3xx`. Both look hand-written (stack-frame calling convention, inline `nop` padding, an `iretd` handler).
   - The C wrapper above it computes the divisor as 1,193,180 / rate (`0x1234DC`). It also treats a rate of `0xFF00` as "DOS rate" (divisor `0xFFFF`).
   - The only caller is the game's sound initialisation: UFO2P `func_000B5950` and TACP `func_000AF770`. They start the timer at the DOS rate and register **one** event at **30 Hz**, whose callback comes from the loaded sound driver's init structure.
   - No game code outside the library reads the library's timer state.
   - The data object holds the strings `hmidrv.386`, `hmidet.386` and `HMI*.386 File Open Failure`, so this is very likely the HMI sound system [ASSUMED: the HMI SOS API names].
3. **A public claim that matches this.** OpenApoc PR #1688 (andremmfaria, opened 2026-09-13, still open) says in its description:
   - the original's main loop busy-waits on the BIOS clock, which pins it to 1193182/65536 = 18.2065 Hz;
   - the loop adds a speed value into a sub-second accumulator, and 36 units make one game second;
   - so "36 ticks per second" is a fixed-point fraction, and nothing in the original runs at 36 Hz.

   Our scan confirms the first half (the BIOS tick is the time base, with UFO2P `func_00011430` and TACP `func_00011500`/`func_000116B0` as the readers). We have **not** yet found the 36-unit accumulator or the speed table. [CITED: https://github.com/OpenApoc/OpenApoc/pull/1688]
4. **Where to look next (for the spike).**
   - Among the 28 UFO2P callers of `func_00011430`, look for the cityscape loop: `func_00022EF0` (4,366 bytes, called from `func_00022040`; it reaches a `while (ticks < target)` wait in `func_00026B80`) is the first candidate.
   - `func_000ACDC0` indexes a table at `0x1303E0` by a small selector and calls `clock()`. It is a candidate for the speed table.
   - UI strings `Slow speed` / `Normal speed` / `Double speed` / `Quadruple speed` sit in UFO2P's text blob. Find their (section, index) and the `get_text` call sites that use them (Q2).

The owner tells OpenApoc, not an agent (auto-memory `notify-owner-997-tick-rate`, `docs/clean-room.md`).

---

## Summary

**Locating is easy; the D-02 depth is what makes Tier 1 big.** The LE fixups plus capstone give a deterministic call graph for both EXEs with no Ghidra and no game files in CI. Strings and data tables lead straight to entry functions, but by two different routes. File names and data tables have direct fixup references. Almost all UI text goes through one indexed `get_text(section, index)` function: UFO2P `func_00063800` (180 direct callers), TACP `func_0005B360` (88 callers).

OpenApoc's CD-build data-table offsets carry over to the installed build at the **same linear address**: 380 of 386 data-object pages are byte-identical and all 47 measured tables matched. So D-42's "re-locate by signature" is only needed for code addresses, not for data. [VERIFIED: scratch reloc scripts]

**The headline risk for the planner and the owner is scale.** Per-function transitive closures are bimodal: the median is 3-4 functions, but about 10% of functions reach most of the EXE.

| | UFO2P | TACP |
|---|---|---|
| Functions reachable from `main_` | 94.7% (direct calls + code pointers + pointer tables) | 96.9% |
| Draft Tier 1 entries (#997 tick readers + the `scenario/unitr.dat` battle-result hand-off of #263-1), direct calls only | 392 functions | 943 functions |
| Same, with pointer edges | 895 functions | 1,122 functions |

With pointer edges, draft Tier 1 is about **2,000 of 3,079 game functions (65%)**. D-05's "only Tier 1 must match in Phase 7" therefore cuts much less than the owner was told. TACP is worse because a 120-function strongly connected component (160 with pointer edges) sits under almost every battle function, and both tick readers and the unit-results writer reach it. The owner needs these numbers before signing Tier 1 (Risk R1). A second risk is hand-written assembly. About 14% of game rows (213 UFO2P, 216 TACP) start off the 16-byte alignment wcc386 uses, and the ones inspected are clearly assembler or third-party library code: the VESA blitters in UFO2P `u_000161b4` and the sound library. These sit inside every UI closure, and the hard rule forbids inline asm (Risk R2).

**EXPERIEN.DAT, BRAIN.DAT and WEAPEXP.DAT are the Learning AI files, not agent training.** UFOpaedia lists them under "Learning AI" [CITED: https://www.ufopaedia.org/Apocalypse]. They belong to #265 (battle AI) and Phase 8's `learning-ai.md`. The agent-training hand-off for #263-1 ("Agent Training from Battlescape") is `scenario/unitr.dat`: TACP `func_000156A0` writes it and UFO2P `func_000B2A90` reads it.

**Primary recommendation:**
- Build one stdlib call-graph module over the existing `contextpack.CallIndex` plus code-pointer and pointer-table edges.
- Keep `config/mechanics.toml` hand-edited: items, tiers, entries with evidence, sign-off.
- Commit a generated, drift-tested `config/mechanics-members.csv` (exe, address, items) so progress.py and speclint work in CI from committed data.
- Run the spike as designed in Q2. Expect **PARTIAL**: the method works, but the tick rate needs the BIOS-tick route and the UI strings need the `get_text` route, not raw string xrefs.
- Put the scale question to the owner at the Tier 1 sign-off checkpoint.

## Project constraints (from CLAUDE.md and rules)

- Never commit game files, disassembly or build output (`orig/`, `asm/`, `build/`, `third_party/`). The members file holds addresses and item ids only.
- Never modify `orig/`, the hash manifests or build scripts to make a check pass.
- A matched function stays byte-identical: no inline assembly to force a match. This is the reason Risk R2 needs a ruling, not a workaround.
- Tooling is stdlib Python 3.14 (progress.py stays 3.12-syntax, stdlib, `python3 -I`), TDD, ruff clean. Real-file tests skip without `orig/`. CI has no game files.
- Committed data files are written with `write_atomic` (`tools/reverseapoc/fileio.py:17`).
- No OpenApoc contact. A #997 finding goes to the owner only. Nothing is copied from OpenApoc code or comments (GPL): offsets are used as locators in a local script, never committed as a table (Q3).

---

## Q1. Call-graph data and the call-tree builder

### What exists

| Source | What it carries | Edges? |
|---|---|---|
| `config/<exe>/functions.csv` | header `start,end,name,kind,unit,evidence` [VERIFIED: config/ufo2p/functions.csv:2]; kinds `KINDS = ("game", "runtime", "thunk", "data-in-code")` [VERIFIED: tools/reverseapoc/functions.py:57] | No. The `evidence` column records why a start exists (`call`, `fixup`, `runtime`, `ghidra`), not who calls it |
| Row counts | UFO2P: 1,549 game, 4 thunk, 259 runtime, 80 data-in-code. TACP: 1,519 game, 7 thunk, 278 runtime, 70 data-in-code [VERIFIED: awk count this session] | |
| `build/ghidra/<exe>/functions.raw.csv` | header `entry,body_min,body_max,addresses,ranges,thunk,calling_convention,name` [VERIFIED: build/ghidra/ufo2p/functions.raw.csv:1]; 1,408 / 1,498 rows | **No** references or call edges. Ghidra drafts exist for only 11 / 13 pilot functions (`asm/<exe>/ghidra/`) |
| `tools/reverseapoc/discover.py` | recursive descent seeded from the entry, runtime starts and code-pointing off32/ptr16:32 fixups; jump tables as data-in-code (L13-17, L206-225) | Collects call **targets** as start evidence (`add_start(target, EVIDENCE_CALL)`, L201-202) but keeps no caller-to-callee edges |
| `tools/reverseapoc/contextpack.py` `CallIndex` | `_WALKED_KINDS = (KIND_GAME, KIND_THUNK)` [VERIFIED: contextpack.py:351]. `_row_callees` walks each row with `asm.walk` and keeps direct call/jump targets that are other rows' starts (a jump there is a tail call) (L505-513). `asm.branch_target` lets an LE rel32 fixup on the field win (asm.py:142-147) | **Yes, direct only:** UFO2P 5,288 edges, TACP 4,885. No code-pointer or table edges. The driver already builds it once per EXE (`driver.py:2586`) |
| `tools/reverseapoc/le.py` `Fixup` | `src_va, kind, target_va, target_obj, target_off, size` (le.py:150-156) | Source of the pointer edges below |
| `asm/<exe>/*.s` | per-function listings (1,894 UFO2P files) | Derived from the same LE; never read by tooling for edges |

Object layout: UFO2P code `0x10000-0xCFADD`, data `0xD0000-0x251E20`; TACP code `0x10000-0xD254F`, data `0xE0000-0x33F0B0`; entry UFO2P `0xC0784`, TACP `0xC28B0` (inside the runtime `cstart`; `main_` is UFO2P `0x00010010`, TACP `0x000102A0` per symbols.csv) [VERIFIED: le.py objects printed this session].

### Pointer edges measured (off32 / ptr16:32 fixups)

| Kind | UFO2P | TACP | Builder rule |
|---|---|---|---|
| code to a code-row start (`mov`/`push offset func`: callbacks, qsort comparators, UI button handlers) | 427 fixups, 343 distinct edges | 388, 336 | edge `src row -> target row`, kind `pointer` |
| code to the middle of a game row | 243 | 220 | **investigate**: either a jump-table base inside a row or a missed function start. Report, do not guess |
| code to the middle of data-in-code | 93 | 80 | jump tables (intra-function, already handled by discover/asm) |
| data to a code-row start (function-pointer slots) | 67 slots in 13 runs; 10 runs referenced from code | 35 slots in 12 runs; 8 referenced | edge from every code row that references the table span to every slot target, kind `table` |
| data to the middle of a code row | 64 | 64 | report |
| unreferenced pointer tables (orphan roots) | 6 targets | 6 targets | list as "unreached roots" for review |

### Reachability (from `main_`, game + thunk rows; runtime and data-in-code excluded per D-02)

| Edge set | UFO2P functions | UFO2P bytes | TACP functions | TACP bytes |
|---|---|---|---|---|
| direct | 1,128 / 1,553 (72.6%) | 85.4% | 1,224 / 1,526 (80.2%) | 92.4% |
| + code pointers | 1,412 (90.9%) | 96.5% | 1,479 (96.9%) | 99.4% |
| + pointer tables | 1,471 (94.7%) | 97.6% | 1,479 (96.9%) | 99.4% |
| + orphan tables | 1,479 | | 1,488 | |
| game rows with no incoming edge at all | 37 | | 35 | |

Per-function closure (all edges), percentiles p50/p75/p90/p95/p99:
- UFO2P: 3 / 137 / 293 / 870 / 968 (max 1,471). 135 functions reach more than 30% of the EXE.
- TACP: 4 / 33 / 1,120 / 1,120 / 1,174 (max 1,479). 217 functions reach more than 30% of the EXE.
- With direct edges only: UFO2P 3 / 103 / 182 / 270 / 453; TACP 4 / 29 / 941 / 941 / 966.

Largest strongly connected component:
- UFO2P: 9 functions on direct edges, 32 on all edges.
- TACP: 120 functions (110 KB) on direct edges, 160 on all edges, around `0xBCDC0..0xBF980`. Any TACP function that reaches it pulls in about 941 functions. Example path from the `scenario/savegame.dat` writer (9 hops): `0x78720 -> 0x3DD80 -> 0x3D0B0 -> 0x3BC00 -> 0x591F0 -> 0x58DD0 -> 0x116B0 -> 0x45ED0 -> 0xBCDC0 -> 0xBDB20`.

Most-called game functions: UFO2P `0x63800` (`get_text`, 180 callers), `0x27020` (146), `0x16864` (105, assembler blitter), `0x5CD00` (101, looks like `random(n)`); TACP `0x5B360` (`get_text`, 88), `0x1F080` (68).

### Recommendation

- **Build a new stdlib module `tools/reverseapoc/callgraph.py`** (TDD). It reuses `CallIndex` for the direct edges and adds typed edges:
  - `pointer`: an off32/ptr16:32 fixup whose source lies in a game or thunk row and whose target is another row's start.
  - `table`: data-object pointer slots grouped into runs (slots at most 16 bytes apart in the measurement; the plan pins the rule with tests), wired from each code row with an off32 fixup into the run's `[first slot, last slot + 4)`.
- **Do not use Ghidra for edges.** Its export has none, it is not in CI, and P4 already says bytes and relocations come from le.py. Ghidra drafts stay a reading aid for single functions.
- **Thunks** are walked like game rows. A thunk to a runtime row (UFO2P `func_000C1544` jumps to `__delay_`) ends at the runtime row.
- **Runtime rows** are leaves: never members, never walked (D-02). Callbacks from the runtime into game code (qsort comparators, `atexit`) arrive as `pointer` edges from the game code that passes them.
- **Data-in-code rows** are never members (D-02). Jump-table case labels stay inside their function (discover/asm already handle this).
- **Unresolvable indirect calls** (`call [reg]`, `call [mem]` with no fixup) are counted per function and listed in the members file's report, never guessed. Let `mechanics.toml` carry hand edges (`[[edge]] from, to, evidence`) for cases a reader proves, so the closure stays reproducible.
- **Closure semantics.** The members of an item are the union of the closures of its entries over `direct + pointer + table` edges. Also store which edge kinds put each member in, so the owner can see what a pointer edge adds (D-02 says "full transitive", and pointer edges add about 500 UFO2P functions to Tier 1).

---

## Q2. String and data-xref locating, the timer, and the 1-day spike

### Strings

| | UFO2P | TACP |
|---|---|---|
| NUL-terminated ASCII strings of 4+ characters in the data object | 3,800 | 2,227 |
| ... with an exact-address LE fixup reference | 1,095 | 592 |

- **File names and format strings** have direct references, so `string -> fixup -> code row` works at once. Examples: `scenario/unitr.dat`, `TACDATA/EXPERIEN.DAT`, `savegame/savegame.00`.
- **UI text has no direct references.** It sits in one sectioned blob, and code reaches it only through `get_text(section, index)`:
  - UFO2P `func_00063800` reads a section-pointer table at `0xF3794` (50 sections; a debug routine right after it loops to 50). It walks `index` NUL-terminated strings.
  - TACP `func_0005B360` does the same from `0x292D18`.
  - So a UI string is located by:
    1. computing its (section, index) from the table and the blob;
    2. finding the `get_text` call sites whose immediate arguments match (Watcom passes them in `eax`, `edx`; recover the last `mov eax/edx, imm` or `xor reg, reg` in the same basic block);
    3. reporting computed indexes (base + i loops) as "partial".
- OpenApoc's 12 `*_STRTAB` offsets land in that blob, and all 12 have **0** direct code references. That confirms this route is the only way to them.

Training and speed strings found (each tagged with its data address; all in the `get_text` blob, no direct refs):
- `Combat training (efficiency=` `0xF0386`;
- `Psionic training (efficiency=` `0xF0368`;
- `Not assigned to training` `0xF034F`;
- `No training facilities in base` `0xF08C2`;
- `(Android training not possible)` `0xF12B6`;
- `Slow speed` / `Normal speed` / `Double speed` / `Quadruple speed` `0xF14BF..0xF14E4`.

A plain `android` string at `0xD2C50` has a direct ref from UFO2P `func_0009B840`.

**Hand-off files between the two EXEs** (direct refs; these are the best entry evidence for cross-EXE items):

| File | UFO2P | TACP |
|---|---|---|
| `scenario/unit.dat`, `object.dat`, `diplo.dat` | written by `func_000ACD70` | read by `func_00014EA0` |
| `scenario/unres.dat` | `func_000ACDC0` | read by `func_00014EA0` |
| `scenario/unitr.dat` (unit results) | read by `func_000B2A90` (called from `main_`) | written by `func_000156A0` (called from `main_`) |
| `scenario/diplor.dat` | | written by `func_000156A0` |
| `scenario/savegame.dat` | `func_000A3BA0`, `func_000A49D0` | `func_00078720`, `func_000788F0` |
| `TACDATA/EXPERIEN.DAT`, `BRAIN.DAT`, `WEAPEXP.DAT` (Learning AI) | `func_000A5F40`, `func_000A6040`, `func_000A61E0` | EXPERIEN `func_00078FE0`, `func_00079050`; BRAIN `func_00014AF0`, `func_000B20B0` |

TACP also references a `TRAIN` string (`0xE00F4`) from `main_`, probably a command-line switch. The spike checks it.

### Timer

Candidate PIT divisors (1,193,182 Hz input clock; the game's own code uses 1,193,180):

| Rate | Divisor | Exact rate |
|---|---|---|
| 18.2 Hz (DOS default) | 65,536 (0x10000, written as 0) | 18.2065 Hz |
| 36.4 Hz | 32,768 (`0x8000`) | 36.4130 Hz |
| 60 Hz | 19,886 (`0x4DAE`) | 60.0011 Hz |
| 72 Hz | 16,572 (`0x40BC`) | 71.9999 Hz |
| 144 Hz | 8,286 (`0x205E`) | 143.9998 Hz |
| 30 Hz (the sound event found) | 39,772 (`0x9B5C`, from 1,193,180) | 30.0005 Hz |

Paths found [VERIFIED: scans this session]:
- **INT 8 install:** DPMI `int 31h` AX=`0204h`/`0205h` with BL=8, and the DOS fallback `int 21h` AX=`3508h`/`2508h`. They live only in the sound-library units: UFO2P `0xC8F03`, restore at `0xC901D`; TACP `0xCC213`, `0xCC32D`.
- **PIT programming:** UFO2P `0xC8EBD`, `0xC8F03`, `0xC901D`; TACP `0xCC1CD`, `0xCC213`, `0xCC32D`.
- **Other ISRs:** UFO2P `func_000B71E0` (TACP `func_000A56B0`) is a keyboard handler: it reads port `0x60` in `func_000B7740`, and its vector is installed via `_dos_setvect_`.
- **Runtime clocks:**
  - Watcom `clock()` reads the DOS time through `intdos` `2Ch`. UFO2P has 6 game callers (UI waits of 100 clocks and a 20-second timer).
  - `delay()` has 6 callers through thunk `0xC1544`, all UI animation waits.
  - **BIOS INT 1Ah via `int386_`** (UFO2P `0x11430`; TACP `0x11500`, `0x116B0`) is the game's time base (finding above).

**Lesson for the spike:** the "PIT / INT 8 setup" route that D-03 names leads to the sound timer, not to the game tick. The working route is `int386(0x1A)` → its callers → the time-advance loop. That is the main reason to expect PARTIAL.

### The 1-day spike: `.planning/spikes/007-locate-997-training/`

**Question (frontmatter `validates`).** Given UFO2P.EXE and TACP.EXE, their LE fixups and the committed functions.csv, when the time base, the UI strings (through `get_text`) and the data-table and hand-off-file xrefs are followed, then:
- the #997 time-advance code and its rate constants are located in both EXEs;
- the #263-1 battle-to-agent stat rule (incl. androids) is located;
- and the same method gives an entry function for most remaining D-01 items.

**Stack.**
- Stdlib, with one stated deviation recorded in the README: decoding goes through `reverseapoc.x86` (the pinned capstone, a shared input like `le` and `iso9660`), because a raw opcode scan cannot find instruction boundaries.
- Facts under test are never taken from the module that produced them: the spike rebuilds direct edges itself and cross-checks `contextpack.CallIndex`.
- Run with `uv run python .planning/spikes/007-locate-997-training/<script>.py`.

**Scripts** (one per question; `PASS/FAIL <file> <claim> <detail>`, `ALL PASS` / `N FAILED`, exit 1 on any FAIL):

| Script | Time | Claims (EXPECTED dict copied from this research) |
|---|---|---|
| `q1_timebase.py` | 1 h | PIT/INT 8 sites only in the sound-library span (counts above); `int386(0x1A)` readers at UFO2P `0x11430`, TACP `0x11500` + `0x116B0`; caller counts 28 / 35 / 10; no direct `0x46C` read |
| `q2_tickrule.py` | 2.5 h | the loop that waits on the tick and advances game time by a speed-indexed amount, in each EXE (address, the speed-table address, the accumulator modulus). Separate claims: "accumulator modulus is 36" (PR #1688) and "the speed table has one entry per speed label" (4 labels found in UFO2P's blob: Slow/Normal/Double/Quadruple; the cityscape time-compression buttons are counted separately). Each PASS/FAIL. A FAIL is a finding, not an error |
| `q3_training.py` | 2 h | `scenario/unitr.dat` writer TACP `0x156A0` and reader UFO2P `0xB2A90`; the stat-update function(s) in UFO2P reached from the reader; the android branch (agent-type test near the `(Android training not possible)` `get_text` site and the `android` ref `0x9B840`); TACP accrual sites (writes into the unit-result fields before `0x156A0`) |
| `q4_strings.py` | 1 h | `get_text` section table decoded (50 / N sections); arg recovery succeeds for at least 80% of call sites (measure); for 12 sampled Tier 2-4 items, an entry is found by string or table (count) |
| `q5_tables.py` | 0.5 h | OpenApoc CD offsets (fetched into the scratch area, never committed) map to the same linear address; 35 UFO2P + 12 TACP tables byte-identical; 23 / 10 have code refs |
| `q6_callgraph.py` | 0.5 h | the Q1 reachability table reproduced; direct edges equal `CallIndex`'s |
| README + MANIFEST | 0.5 h | |

**Prove the checker can fail.**
- (a) Rerun each script with one planted wrong EXPECTED value (for example a tick reader at the wrong address) and record that it FAILs.
- (b) Run an in-memory mutant: zero the `0x1A` immediate in a copy of the flat image. `q1` must then report the reader as missing.
- (c) Rerun `q5` with a one-byte change in a copied table and check that `same VA` turns FAIL.

**Game data never leaves the script.**
- Strings are matched inside the script by keyword and reported by address and keyword label only (spike CONVENTIONS forbid printing game bytes).
- No instruction text is printed: report addresses, counts, booleans and constants that are protocol facts (interrupt numbers, divisors, moduli).
- Read the disc image in memory, as spike 003 does (`ISO9660.open(game / "cd.iso")`; Steam install at `C:\Program Files (x86)\Steam\steamapps\common\XCom Apocalypse`, present on this machine).

**Verdict (D-03).**
- **VALIDATED:** q2 and q3 both PASS (tick rule and training rule located with addresses in the right EXEs), and q4 finds an entry for at least 10 of the 12 sampled items by strings or xrefs.
- **PARTIAL:** one of q2/q3 PASSes, or q4 finds 6-9 of 12. D-03 then adds call-graph walking from the OpenApoc data-table offsets. q5 already shows the offsets need no signature search for data.
- **INVALIDATED:** neither q2 nor q3 locates its rule, or q4 finds fewer than 6 of 12.
- My expectation: PARTIAL to VALIDATED, because raw string xrefs alone fail for UI text and the PIT route fails for #997, but the `get_text` and BIOS-tick routes work.

**Outputs.**
- `README.md` with frontmatter `spike: 007`, `idea: mechanics-first-decompilation`, `name: locate-997-training`, `type: standard`, `validates: "Given ... when ... then ..."`, `verdict`, `related: [003]` (disc reading), `tags: [mechanics, 997, training, get_text, bios-tick, d-01, d-03]`.
- A new idea block `### mechanics-first-decompilation` in MANIFEST "Ideas" with its Requirements (read-only; addresses/counts only; OpenApoc offsets used as locators, not committed).
- A MANIFEST row.
- Any #997 result goes to the owner at once, with addresses and "matched code backs it: no".

---

## Q3. OpenApoc data-table offsets (D-42 re-location)

- **What OpenApoc gives.** `tools/extractors/common/*.h` define `*_OFFSET_START/_END` as **file offsets** in the CD v1.00 EXEs (`DataChunk` does `file.seekg(start_offset)`). `ufo2p.cpp` checks `expected_ufo2p_crc32 = 0x4749ffc1` and only logs on mismatch. The constants are spread over `research.h`, `agent.h`, `organisations.h`, `economy.h`, `facilities.h`, `vehicle.h`, `vequipment.h`, `baselayout.h`, `building.h`, `crew.h`, `bulletsprite.h`, `audio.h`, `ufopaedia.h` and `aequipment.h`, not in `ufo2p.h`/`tacp.h`, which only declare the chunks. [CITED: github.com/OpenApoc/OpenApoc/tree/master/tools/extractors/common, fetched read-only via `gh api`]
- **What is known locally.**
  - `config/targets.toml` `[[cd_builds]]`: UFO2P.EXE path `XCOM3/UFOEXE/UFO2P.EXE`, size 1702206, `crc32 = 0x4749FFC1`; TACP.EXE `XCOM3/TACEXE/TACP.EXE`, size 3170298, `crc32 = 0xFEBBE39E` [VERIFIED: config/targets.toml:45-59].
  - `docs/toolchain.md` L25-37: both builds are on the 1997 disc, the installed build is primary (D-42), and OpenApoc offsets describe the CD build.
  - `cd.iso` is present in the Steam install, and `reverseapoc.iso9660.ISO9660` reads it in memory (spike 003 pattern).
- **Measured.** File offset → CD linear address (through the CD LE page map) → installed build:
  - The CD and installed **data objects have the same base and end** (UFO2P `0xD0000-0x251E20`, TACP `0xE0000-0x33F0B0`).
  - 380 of 386 UFO2P data pages are byte-identical, and only 258 data bytes differ.
  - All 35 UFO2P tables and 12 TACP tables are byte-identical at the **same** linear address (2 TACP sprite offsets did not map to page data).
  - The code objects differ (CD UFO2P code ends `0xCE8AD`, installed `0xCFADD`).
- **Code addresses do need signatures.** The `FUN_` addresses in OpenApoc PR #1685 (`0x14854`, `0x9379C`, `0x93A30`, `0x5FAF0`) are not function starts in our installed functions.csv. They fall inside `func_00014210`, `func_000932E0` and `func_0005F9B0`. A fixup- and rel32-masked 48-byte signature from the CD image found 1 of 4 uniquely (`0x14854` → installed `0x14A30`). Their base convention is unknown (Open Question 3). Do not rely on them without a per-address check.
- **Xref yield** (code rows with a fixup into the table span):
  - 23 of 35 UFO2P tables have code refs, and all 12 that have none are string tables, so they need the `get_text` route.
  - 10 of 12 TACP tables have code refs.
  - Examples: `ECONOMY_DATA1/2/3` (11/8/9 code rows), `RESEARCH_DATA` (14), `VEHICLE_EQUIPMENT_DATA` (53), `ORGANISATION_STARTING_RELATIONSHIPS_DATA` (1: `func_00099710`), the infiltration-speed tables (`func_0006F3C0`, `func_0006FC80`, `func_00089360`), `CREW_ALIEN_BUILDING` (`func_000AEAB0`, `func_000AF130`), TACP `AGENT_EQUIPMENT_DATA` (82), `DAMAGE_MODIFIER_DATA` (4).
- **Recommendation.**
  - The re-location tool (or spike script) maps a CD offset to a VA, asserts the installed bytes at that VA equal the CD bytes, and records the installed VA. On a mismatch it falls back to a masked signature search, and it never trusts a single hit without the byte check.
  - Commit only our own result: installed addresses in `mechanics.toml` evidence, cited as "OpenApoc extractor table `RESEARCH_DATA`, re-located by VA identity". Never commit a copy of OpenApoc's offset list (GPL-licensed header; D-21 and Phase 8 source rules).

---

## Q4. Item → EXE and entry evidence, with a proposed in/out line per tier

Legend for evidence: **H** = hand-off file (direct ref), **T** = OpenApoc data table (VA identity, Q3), **S** = UI string via `get_text`, **F** = file-name string, **B** = BIOS-tick / call graph, **D** = save-game / data field the spike must trace. EXE: U = UFO2P (cityscape), T = TACP (battlescape).

### Tier 1 (sign-off first)

| Item | EXE | Draft entries | Evidence |
|---|---|---|---|
| **#997** tick rate (also #263-21 and #264-2, recorded as `duplicate_of = "997"`) | U + T | U `0x00011430` (INT 1Ah reader), the cityscape time-advance loop (candidate `0x00022EF0`); T `0x00011500`, `0x000116B0`, the battle loop | B; S (`Slow/Normal/Double/Quadruple speed`); PR #1688 claim |
| **#263-1** agent training from battlescape, incl. androids | T writes, U applies | T `0x000156A0` (`scenario/unitr.dat` writer) + accrual sites; U `0x000B2A90` (reader) + the stat-update callee; android branch near `0x0009B840` and the `(Android training not possible)` site | H, S, D |

Not Tier 1 despite the spike prompt: EXPERIEN/BRAIN/WEAPEXP.DAT are the Learning AI (Tier 4, #265-1..8).

### Tier 2: #263 (remaining)

| # | Proposed | EXE | Evidence |
|---|---|---|---|
| 2 infiltration graph | in | U | T (3 infiltration-speed tables), S |
| 3 aliens move building to building | in | U | T (`ALIEN_BUILDING_NAME_STRTAB` via S), B |
| 4 eggs/chrysalis hatch | in | U | T (`CREW_ALIEN_BUILDING`), S |
| 5 city economy, wages, budgets | in (ticked, numbers useful) | U | T (`ECONOMY_DATA1-3`, `BUILDING_COST_STRUCT`) |
| 6 weekly funding | in | U | S (funding screen), D |
| 7 diplomacy | in | U | T (`ORGANISATION_STARTING_RELATIONSHIPS_DATA`), the two 28x28 matrices of PR #1685 (data addresses carry over by VA identity [ASSUMED until checked]) |
| 8 org agents moving, mission generation | in | U | T (`ORGANISATION_DATA`), S |
| 9 bribes | in | U | S |
| 12 transport repaired at base | in | U | T (vehicle tables), S |
| 13 agent training on base | in (ticked; the rule is the cityscape half of training) | U | S (`Combat training (efficiency=`) |
| 15 transfer of agents/items | in | U | S |
| 22 map spawn/variation | in | U + T | F (`scenario/*.dat`, `sections.dat`, `tactical.map` written by U `0xB0F70`/`0xB4590`, read by T) |
| 25 UnitAI (battle) + vehicle/UFO tactics (city) | in | T + U | Learning AI files, B |
| 26 "Apocalypse" mission | in | U | S, B |
| 27 large UFO attack | in | U | S, B |
| 28 Overspawn carry/deploy | in | U | S |
| 10 vehicle location drag-and-drop, 11 hover, 14 UFOpaedia display, 16 alert screen, 17 tooltips, 18 text editing | **propose out** (UI chrome; no rule or number OpenApoc needs) | U | |
| 19, 20, 23, 24 | out (D-01) | | |
| 21 | duplicate of #997 | | |

### Tier 3: #264

| # | Proposed | EXE | Evidence |
|---|---|---|---|
| 3 nightly score and finances | in | U | S |
| 4 weekly funding assessment | in | U | S (shares #263-6 functions) |
| 5 victory/defeat | in | U (+T mission end) | S |
| 6 alien takeover | in | U | S |
| 7 portal locations, 8 portal movement | in | U | S, B |
| 9 graphs and stats | in | U | S |
| 10 medals, per-battle stats | in (ticked; rules useful) | T + U | H (`unitr.dat`), S |
| 11 umbilical collapse | in | U | S, B |
| 12 stop UFO growth, 13 UFO mushrooms | in | U | B, S |
| 15 org vehicle buy/sell, 17 illegal flyers, 18 craft retreat | in | U | T (`ORGANISATION_VEHICLE_PARK_DATA`, vehicle tables) |
| 16 treaties, raids, storming | in | U (+T raids) | T, H (`diplo.dat`/`diplor.dat`) |
| 19, 20 ground-vehicle lanes, drive side | in (D-01 borderline) | U | B (vehicle movement) |
| 21 dynamic music | in (D-01 borderline) | U + T | F (music file names), B |
| 25 daily report | in | U | S |
| 28 starting agent count | in (ticked; the number is useful) | U | D (new-game init, `ORGANISATION_DATA` ref `0xBA360`) |
| 24 message-history scroll, 26 camera follow, 27 onHover | **propose out** (UI chrome) | | |
| 1, 22, 23, 29-33 | out (D-01) | | |
| 2 | duplicate of #997 | | |

### Tier 4: #265

| # | Proposed | EXE | Evidence |
|---|---|---|---|
| 1-8 battle AI (behaviour, modes, wounds, medkits) | in | T | F (Learning AI files: T BRAIN `0x14AF0`/`0xB20B0`, EXPERIEN `0x78FE0`/`0x79050`; U `0xA5F40`/`0xA6040`/`0xA61E0`), T (`AGENT_*` tables) |
| 9 cityscape AI | in | U | B |
| 10, 11 alien movement in the city | in | U | B, T |
| 12 agent-to-vehicle retention | in (borderline; state rule) | U | D |
| 13 name generator | in (D-01) | U | S (name sections in the blob) |
| 14-18 | out (D-01) | | |

- **Items in both EXEs:** #997, #263-1, #263-22, #263-25, #264-5, #264-10, #264-16, #264-21.
- **Items likely in no game code:** none outright, but the two-EXE pipeline (`scenario/*.dat`) means some rules are pure data passed through; the member list shows that.

---

## Q5. `config/mechanics.toml` schema (proposal)

Two files:
- a **hand-edited** `config/mechanics.toml`: the owner's and Claude's decisions;
- a **generated** `config/mechanics-members.csv`: the tool's output, "do not edit", drift-tested.

This follows the existing split between generated `functions.csv` and drafted/hand-cut `units.csv`. One file mixing both would need a TOML writer that rewrites the owner's sign-off lines. The stdlib has no TOML writer.

```toml
# config/mechanics.toml: which functions answer which OpenApoc checklist items (DEC-01).
# Hand-edited. Members are generated into config/mechanics-members.csv by
# `uv run reverseapoc mechanics --write`; do not list members here.
schema = 1

[[tier]]
id = 1
title = "Tick rate and battlescape training"
signed_off_by = "ayrtondenner"        # absent until the owner signs (blocking checkpoint, D-04)
signed_off_date = 2026-11-02          # TOML local date
members_sha256 = "..."                # SHA-256 of this tier's rows in mechanics-members.csv at sign-off

[[item]]
id = "997"                            # "<issue>-<n>" for checklist items, "997" for the issue itself
issue = 997
title = "Ticks per second / frames per second"
url = "https://github.com/OpenApoc/OpenApoc/issues/997"
tier = 1
scope = "in"                          # in | out | duplicate
exes = ["ufo2p", "tacp"]

[[item]]
id = "263-21"
issue = 263
title = "Resolve issue #997"
url = "https://github.com/OpenApoc/OpenApoc/issues/263"
tier = 2
scope = "duplicate"
duplicate_of = "997"

[[item]]
id = "263-19"
issue = 263
title = "Map editor"
url = "https://github.com/OpenApoc/OpenApoc/issues/263"
tier = 2
scope = "out"
reason = "OpenApoc-only tooling (D-01)"

[[entry]]
item = "263-1"
exe = "tacp"
address = "0x000156A0"                # functions.csv format, a game/thunk row start
evidence = "file"                     # file | table | string | bios-tick | call-graph | data-field | hand
detail = "writes scenario/unitr.dat"  # short, our words; no game bytes beyond <=40-char identifiers
source = "spike 007 q3"

[[edge]]                              # optional hand edge for an indirect call a reader proved
exe = "ufo2p"
from = "0x000XXXXX"
to = "0x000YYYYY"
evidence = "call through table at 0x... (spike 007)"
```

`config/mechanics-members.csv` (generated, LF, sorted by exe then address):

```
# generated by: uv run reverseapoc mechanics --write; do not edit
exe,address,items,tiers,via
ufo2p,0x00011430,997,1,entry
ufo2p,0x00063800,263-1;263-2;997,1;2,direct
tacp,0x0005B360,263-1;265-1,1;4,pointer
```

- **One row per function (D-02 shared-function rule).** `items` lists every item that reaches it (`;`-joined, sorted), and `tiers` the tiers they belong to. The function's tier for scheduling is `min(tiers)`.
- **`via`** is the weakest edge kind on the shortest path from any entry: `entry`, `direct`, `pointer`, `table` or `hand`. It shows how much of a tier rests on pointer edges.
- **Never store names.** D-19 renames change names. Readers join on the address with `functions.csv`, `symbols.csv` and `status.csv`.
- **Members must be committed, not computed on the fly.** CI and the Pages runner have no game files. progress.py, `readlint --tier` and Phase 8 speclint must work from committed data. The generator needs `orig/`, so it runs on the host or in the container.
- **Drift test** (real-file, skips without `orig/`): regenerate from the committed `mechanics.toml` plus the LE and compare byte for byte, like `test_functions_csv_has_no_drift` (`tests/test_functions_real.py:185-187`).
- **Schema test** (CI, no game files):
  - every member address is a `game` or `thunk` row of `config/<exe>/functions.csv`;
  - every entry appears in the members file with `via = entry`;
  - every `items` id exists with `scope = "in"`;
  - `duplicate_of` points at an `in` item;
  - a signed tier's `members_sha256` equals the hash of its current rows. Otherwise the tier is "changed since sign-off": the test fails and the owner re-signs.
- **Phase 8 speclint** reads `[[item]]` (id, tier, scope, url) and the members file (addresses, so it can check a spec's function list against `functions.csv` and the gate status).

---

## Q6. DEC-05 data side (what progress.py needs)

progress.py runs in CI with stdlib only, Python 3.12 syntax, `python3 -I`, and cannot import reverseapoc (`tools/progress.py:22-26`). It can read:
- `config/mechanics.toml` with `tomllib`, which is in the stdlib from 3.11;
- `config/mechanics-members.csv` with `csv`;
- `config/<exe>/status.csv` and `functions.csv`, which it already reads.

Per item, it derives from committed data only:
- **functions:** total, matched, partial and unmatched. Join the members by `(exe, address)` with status.csv `start` (matched / partial rows; no row = unmatched, as today).
- **bytes:** the same split, from functions.csv `end - start`.
- the tier, scope, sign-off date and duplicate links.

The page shows `in` items only; duplicates point at their target. Tier totals use the **union** of members, so a shared function counts once per tier, not once per item.

Interfaces to slice 3:
- add both files to `.github/workflows/pages.yml` `on.push.paths` (today it lists `config/*/status.csv`, `functions.csv`, `units.csv`, `tools/progress.py`, `decomphub.progress.json`, `pages.yml`) [VERIFIED: .github/workflows/pages.yml:14-20];
- a missing mechanics file means no section, so synthetic test configs keep working (slice 3 already proposes this).

---

## Risks and open questions

**R1. D-05's Tier 1 is not small.** The owner must see this at the Tier 1 sign-off.
- Draft Tier 1 closures are UFO2P 392 / TACP 943 functions with direct edges, or 895 / 1,122 with pointer edges: 43-65% of all game functions, and about 82% of TACP's game bytes.
- At the pilot rate (3 matches in 40 sessions, about USD 14 a match) that is far beyond one phase.
- The cause is structural: TACP's 160-function component, and UI/drawing hubs in both EXEs.
- **Options for the owner** (a re-ruling of D-02/D-05; research does not choose):
  - (a) Keep the full closure and accept the scale.
  - (b) Members = the closure up to the first "hub" (a function whose own closure exceeds X% of the EXE, or a member of the largest SCC). Hubs are listed as `boundary`: located, not required in Phase 7.
  - (c) Direct edges only. This drops about 500 UFO2P functions but barely changes TACP.
  - (d) A depth limit.

  The members file can carry a `role` column (`core` / `boundary`) for (b) without a schema change elsewhere.
- **Recommendation:** present (a) and (b) with numbers computed by the real tool at the checkpoint.

**R2. Hand-written assembly and third-party library code inside the closures.**
- About 213 UFO2P and 216 TACP game rows are not 16-byte aligned. Two inspected regions are certainly not wcc386 output:
  - UFO2P `u_000161b4` (`0x161B4-0x18970`): VESA blitters, including the 105-caller `func_00016864`;
  - the sound timer (`0xC8E41..`), plus its C wrapper unit `u_000c1b4b`, whose functions also start off alignment.
- Pilot evidence: TACP `func_000C6287`, inside the sound-library unit, capped at 61.87% after 3 sessions (`config/tacp/status.csv`).
- Draft Tier 1 holds 74-132 such rows per EXE.
- They cannot match from C without inline asm, which the hard rules forbid.
- **Needs an owner ruling before Tier 1 sign-off:**
  - mark them excluded like runtime (a new `kind` in functions.csv, written by the `functions` tool with evidence);
  - or match them as separate `.asm` units assembled with Watcom's assembler (a toolchain decision, not inline asm);
  - or leave them unmatched and outside D-05's "every function".
- The planner should add a classification task: alignment plus calling-convention plus `enter`/`pushal`/`iretd` heuristics, with owner review.

**R3. The EXPERIEN.DAT premise in the spike prompt is wrong.** These are the Learning AI files (UFOpaedia). Training goes through `scenario/unitr.dat`. Q3 of the spike tests the corrected premise.

**R4. Mid-row code references** (243 UFO2P / 220 TACP fixups from code into the middle of a game row, and 64 per EXE from data). Each is either a missed function start (a lost edge) or a table base. The call-graph builder must report them. A plan task should classify them before Tier 1 members are frozen.

**R5. Unresolvable indirect calls** (`call [reg]`) are invisible to the closure. Count them per function and resolve them with `[[edge]]` entries only on evidence.

**Open questions**
1. Is the 36-unit accumulator real? The spike's q2 decides it. If found, report it to the owner at once (it changes the #997 answer from "18.2 Hz loop" to "18.2 Hz loop with 36 sub-steps per game second").
2. Does TACP's battle loop use the same BIOS-tick pacing at a different scale? The spike checks it.
3. Which base and build PR #1685's `FUN_` addresses use. They are not function starts in either our installed list or (for 3 of 4) the CD image at face value. The owner decides whether it matters. The data route works without them.
4. Does the members file key `tiers` need to be stored, or can it be derived from `items`? Stored it is cheaper for progress.py and speclint, and drift-tested anyway.
5. The `get_text` arg recovery rate is unknown until q4 runs (estimate: high for constant indexes, low for loops).

---

## Interfaces other slices depend on

| Consumer | Reads | Fields / API |
|---|---|---|
| Driver picker (slice 2) | `mechanics.toml` + members CSV + the live call graph | Signed tiers in `id` order (`signed_off_by` present and `members_sha256` valid). Member keys `(exe, address)` with `min(tiers)`. Callee edges among members come from `callgraph.build(exe)` at run time (orig/ is present on the host): typed `direct/pointer/table/hand`, so the driver can order callees first and compute SCCs itself. API sketch: `mechanics.load(config) -> Mechanics` with `.tiers_signed()`, `.members(tier) -> frozenset[(exe, int)]`; `callgraph.edges(exe, data) -> Mapping[int, frozenset[(int, kind)]]` |
| Claims (slice 2) | members → units through functions.csv `unit` | A unit is claimable for tier N if it holds at least one member of N. Draft Tier 1 touches 137 UFO2P / 232 TACP units (direct) or 211 / 247 (all edges) |
| progress.py coverage (slice 3) | `mechanics.toml` (`[[item]]`, `[[tier]]`) via `tomllib`; `mechanics-members.csv` via `csv` | `id, issue, title, url, tier, scope, duplicate_of`; tier `signed_off_by/date`; members `exe, address, items` |
| `readlint --tier` (slice 3) | same | member addresses → units |
| `stats` (slice 2) | members | optional per-tier split of matches |
| Phase 8 speclint | `mechanics.toml` + members | item ids, tiers, member addresses |
| CI workflows | both files | `pages.yml` path filter; `ci.yml` runs the schema test |

---

## Validation ideas (testable pieces, mostly without game files)

1. **callgraph.py (TDD, synthetic LE).** Build tiny LE images with the existing test builders (`tests/fixtures`, `relocpair.py`) holding:
   - a direct call, a tail jump, a `push offset func` fixup and a data pointer table referenced by a `mov` fixup;
   - a jump table, which must not create edges;
   - a call to a runtime row, which must stop there;
   - a mid-row fixup, which must be reported.

   Assert the typed edge sets exactly. A planted wrong edge must fail.
2. **Closure.** Synthetic graphs with a cycle, a shared callee reached from two items (listed once, both items), and an excluded runtime row. Check that the `via` value is the weakest kind on the shortest path.
3. **Members writer.** Deterministic bytes, sorted, LF, `write_atomic`. Two runs give the same bytes. Malformed `mechanics.toml` is refused: an unknown `scope`, an entry on a non-game row, `duplicate_of` an `out` item, an address not in functions.csv format.
4. **Schema test in CI** (Q5 list), including a planted signed tier whose members changed, which must fail.
5. **Drift test (real files).** Regenerate the members and compare; skip without `orig/`.
6. **Real-file regression pins** (skip without `orig/`):
   - `get_text` decodes 50 sections in UFO2P;
   - UFO2P `func_00011430` and TACP `func_00011500` are the only game rows calling `int386_` with `0x1A` (TACP also `func_000116B0`);
   - reachability from `main_` stays within ±1% of the Q1 table.
7. **progress.py.** Committed-data fixture `mechanics.toml` + members + status.csv → exact per-item counts. A shared function counts once in a tier total. A missing file gives no section.
8. **Spike.** The PASS/FAIL scripts and the planted-failure runs, recorded in its README.

---

## Assumptions log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | The sound timer is HMI SOS (`0xFF00` = DOS-rate sentinel, `RegisterEvent(rate, far callback, handle)`) | #997, Q2 | Naming only; the conclusion that it is not the game clock rests on the xref scan, not on this |
| A2 | The candidate cityscape loop is `func_00022EF0` and the speed table is at `0x1303E0` | #997 | The spike looks elsewhere among the 28 callers |
| A3 | `scenario/unitr.dat` carries the battle stat changes that make #263-1 | Q4 | #263-1 entries move; the spike q3 tests it |
| A4 | The PR #1685 matrices (`0x16EC28`, `0x16F078`) carry over by VA identity like the extractor tables | Q4 Tier 2 | Re-locate by signature instead |
| A5 | Unaligned rows are mostly assembler or library code | R2 | Fewer exclusions needed; classification task settles it |
| A6 | The proposed in/out lines for UI-chrome items | Q4 | Owner rules per tier (D-01, D-04) |
| A7 | The 30 Hz event callback lives in the runtime-loaded sound driver | #997 | None for the #997 answer |

## Environment availability

| Dependency | Needed by | Available | Version |
|---|---|---|---|
| uv / Python | all tooling | yes | Python 3.14.5 |
| capstone | decoding | yes | 5.0.9 (the pin) |
| `orig/` UFO2P.EXE, TACP.EXE | generator, drift test, spike | yes | manifest-checked by `exe_inputs` |
| Steam `cd.iso` | Q3 / spike q5 | yes | `C:\Program Files (x86)\Steam\steamapps\common\XCom Apocalypse\cd.iso` |
| `gh` (read-only issue/PR text) | item list | yes | 2.92.0 |
| Ghidra 12.1.4 | optional drafts only | Docker image (Phase 5) | not needed for edges |

## Security domain

- No authentication, network service or secrets are involved.
- **V5 input validation applies:** `mechanics.toml` and the members CSV are parsed strictly (unknown keys, malformed addresses and non-game rows are refused; the same pattern as progress.py's `_records`).
- **Tampering:** a member list edited by hand is caught by the drift test, and a changed signed tier by `members_sha256`.
- **Information disclosure:** the schema test allowlists fields so no game bytes enter committed files (addresses, ids, short evidence text only).
- OpenApoc headers are fetched to a scratch directory and never executed or committed.

## Sources

- Local measurements this session: scratch scripts (`cg.py`, `scc.py`, `timer.py`, `strs.py`, `reloc*.py`, `tabref.py`, `tier1.py`) over `orig/` and `cd.iso`, via `reverseapoc.check.load_exe`, `le`, `x86`, `contextpack.CallIndex`, `iso9660`.
- Repo files read: `07-CONTEXT.md`, `REQUIREMENTS.md`, `ROADMAP.md` § Phase 7, `spikes/CONVENTIONS.md`, `MANIFEST.md`, spike 003 scripts, `discover.py`, `x86.py`, `contextpack.py` L490-712, `asm.py` L142-147, `le.py`, `functions.py` L57-101, `progress.py` L1-60, `targets.toml`, `docs/toolchain.md`, `docs/research/notes-target-binary-and-toolchain.md` L240-310, `tests/test_functions_real.py`, `tests/test_drift.py`, `.github/workflows/pages.yml`, `.claude/skills/watcom-decomp/SKILL.md`.
- [OpenApoc #263](https://github.com/OpenApoc/OpenApoc/issues/263), [#264](https://github.com/OpenApoc/OpenApoc/issues/264), [#265](https://github.com/OpenApoc/OpenApoc/issues/265), [#997](https://github.com/OpenApoc/OpenApoc/issues/997) (read with `gh`, read-only)
- [OpenApoc PR #1688](https://github.com/OpenApoc/OpenApoc/pull/1688) (tick-rate claim in the description)
- [OpenApoc extractor headers](https://github.com/OpenApoc/OpenApoc/tree/master/tools/extractors/common) (offsets, CRC check)
- [UFOpaedia: Apocalypse](https://www.ufopaedia.org/Apocalypse) (EXPERIEN/BRAIN/WEAPEXP.DAT under "Learning AI"); [Talk: Known Bugs (Apocalypse)](https://www.ufopaedia.org/Talk:Known_Bugs_(Apocalypse))

**Valid until:** about 2026-11-25 (the code facts are stable; the OpenApoc PR state may change).

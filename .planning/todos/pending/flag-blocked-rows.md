---
title: Repair the flag-blocked rows that reach 100% only under another rule
created: 2026-11-14
area: flags
files: config/cflags-proposals.toml
source: near-miss lane review (main session, 2026-11-14)
---

# Seven partial rows at best 100.00% that no proposal can land

Each reaches objdiff 100% only under a non-default rule (`needs flags ...`), and the near-miss lane
leaves them out (picker: best_percent in [minimum, 100)). No proposal for them passed its re-gate,
so `flags approve` cannot land them:

| Row(s) | Proposal | Re-gate failure | Repair |
|---|---|---|---|
| ufo2p func_000520A0, func_000520C0 | F-0028 | candidate C does not compile in the unit (undeclared D_000E12F0, ...) | a candidate with the unit's declarations, then `flags regate` |
| ufo2p func_0005DB80 | F-0029 | compile errors (unk_016A field, undeclared D_00128616) | the same |
| ufo2p func_0008A0C0 | F-0037 | the rule breaks 5 sibling functions in u_00089980 (75%, reloc) | decide how one unit holds functions built under different rules (split the unit?) |
| ufo2p func_000B4B80 | F-0072 | `-5r` breaks matched func_000B4470 in u_000b4470 (92%) | the same |
| tacp func_00088450, func_000AB650 | none | never proposed | `flags propose` from their sweep hits, then regate |

The owner approves landings (`flags approve`); this todo is the work that makes them approvable.

## Update (2026-11-15)

Three of these rows no longer need a rule: Terra matched ufo2p func_000520A0 and func_000520C0
(F-0028) under the default rule on run 20261115-claude-push2, and the targets of the failed
proposals F-0004 (ufo2p func_0004DFD0, Opus) and F-0002 (tacp func_000779C0, Sonnet) were matched
on 20261114-opus-near. Left: func_0005DB80 (F-0029), func_0008A0C0 (F-0037), func_000B4B80
(F-0072), tacp func_00088450 and func_000AB650. Before repairing a rule, give the row a near-miss
pass with a strong model: a better source may match under the default.

## Update (2026-11-19): run 20261118-flags

The near-miss pass the update above asked for ran on Sol (one worker, 4 picks, `build/driver/20261118-flag-picks.txt`). It ENDED `queue exhausted` after 4 sessions:
- **Matched on attempt 1 under the default rule:** ufo2p func_0008A0C0 (F-0037, `ea7d2a60`) and tacp func_00088450 (never proposed, `4c4de2db`). F-0037's unit-split question is moot for this row.
- **Still blocked (parked):** ufo2p func_0005DB80 (F-0029) reached 100% again only under `-4r -ox -s -fpi`, and ufo2p func_000B4B80 (F-0072) only under `-5r -oneatx -s -fpi`. Their repairs in the table above stand.
- **Not in the queue:** `--picks` refused tacp func_000AB650. Its row in `config/mechanics-members.csv` has role `closure` (reached only by item 997's full closure, a member of no item's hub-stopped set), and the tier queue holds only `member` and `hub` rows (`picker.py`: "asm and closure rows are never in a group"), so `refuse_picks` finds it outside the queue. It needs another route to a session: a hand pass, or a pick source that admits closure rows.

Left: func_0005DB80 (F-0029), func_000B4B80 (F-0072) and tacp func_000AB650.

## Update (2026-11-20): measured analysis, read-only (drive running)

Read from `config/*/status.csv` (identical in the checkout), `config/cflags-proposals.toml`,
`progress/attempts.jsonl` and the checkout's `build/driver/` and `build/flags/` records. Nothing
was compiled, so nothing below is a match; each "would" waits for a check after the drive.

### The rows: every `partial` row at best 100.00 today (6), and why each one is held

| Row | Unit (rule) | Blocked by | Evidence |
|---|---|---|---|
| ufo2p func_0005DB80 | u_0005db20 (default) | the unit layout, not the function | 20261118-flags a1 `checks/0002.json`: sweep cell 1 (the default `-4r -s -fpi`) is 100%, reloc ok; check 0001 (default) has the claim at 100% but the unit's matched func_0005E550 drops to 74.56% |
| ufo2p func_0005E500 | u_0005db20 (default) | the same | 20261114-nearmiss4-copilot-haiku-5-5 a2: check 5 exit 0 under the default with func_0005E550 back to INCLUDE_ASM; the gate refused it (`func_0005E550 ... matched in status.csv ... was not landed`) |
| ufo2p func_000B4B80 | u_000b4470 (`-4r -oneatx`, F-0043) | a leading-table length check, not code | 20261118-flags a1 `checks/0001.json`: objdiff 100%, bytes ok, shape equal (89/13/7); the only problem is `0x000B4B80: length differs: ours 32 bytes, original 20 bytes; ours is longer than the row` |
| tacp func_000AB650 | u_000aa940 (default) | no route to a session (role `closure`) | 20261101-023246 func_000AB600 a3 `notes.md` and `checks/0002.c`: AB650's C is 100%, reloc ok, bytes ok **under the default rule**. It is not a flags row |
| ufo2p func_00050A20 | u_000502b0 (`-4r -ox`, F-0071) | cross-function tail merge with matched func_000509C0 | 20261115-terra-credits a1 `notes.md`: check 1 is 100% for the claim, func_000509C0 "merged into its tail" |
| ufo2p func_00050A80 | u_000502b0 (`-4r -ox`) | the same | 20261115-terra-credits a1, check 1 |

The near-miss lane never picks these rows (best_percent is not below 100). The last two were never
on this todo's list; they are here because they sit at 100.00 for a reason that is not a rule.

The seven rows of proposals F-0086..F-0091 (func_00051C70, func_0005EDB0, func_00060BA0,
func_00060BD0, func_000886D0, func_000A3180, func_000B7870) are flag-blocked too. All are
`proposed` with `regate_exit = -1`: `flags regate` (docker) runs before the owner can approve.

### Findings

1. **u_0005db20 wants a filler-emitting rule.** In the DB80 sweep, the cells at 100% emit 161
   bytes under the default and `-ox`, and 176 bytes under `-ot` and `-oneatx`. The row
   0x5DB80..0x5DC30 is 176 bytes. func_0005E500 emits 73 bytes under the default against its
   80-byte row (copilot a1 notes). Under the default rule func_0005E550 breaks (77 bytes against
   96, its `break` jumps outside its own body) whenever DB80 or E500 is in C before it, and E500
   placed after it breaks instead (75.32%). F-0029's rule `-4r -oneatx` fits this. F-0029 failed
   only on compile errors in its candidate (finding 3), and nobody has measured it. Whether
   func_0005E550 and rec15e_table_any_used stay matched under `-oneatx` is open: the re-gate's
   `keeps` measures that.
2. **func_000B4B80 is probably not a `-5r` function.** Under `-4r -oneatx` (the unit's rule) it
   emits 96 bytes, which is the row length: 89 code bytes plus the 7 bytes of filler the
   original has. Under `-5r -oneatx` it emits 89 bytes, with no alignment. The original
   therefore aligns like `-4r`. The 12 extra bytes are in the span of its leading jump table
   D_000B4B6C. The table starts at segment offset 0 in our object, so `-4r` pads 20 to 32 to
   16-align the head. The original table starts at 0xB4B6C (12 mod 16) and needs no pad. The
   07-48b table rule accepts a span that is short by filler, not one that is long by filler.
   `-5r` passes only because it does not align at all. It also breaks matched func_000B4470
   (F-0072 re-gate: 92%, reloc failed), and config/cflags.txt has no `-5r` rule in any of its
   78 lines. Not yet read: the 12 bytes themselves. "Alignment filler" is inferred from the
   lengths and has not been decoded.
3. **`flags propose` builds broken candidates when it merges hits from different attempts.**
   `_merge` (`flags.py`) splices in only the function definition (`contextpack.splice_definition`)
   and drops the hitting file's own structs and externs. Of the 11 proposals that failed their
   re-gate with `compile failed`, 10 hold functions from more than one attempt directory
   (F-0005, F-0014, F-0019, F-0020, F-0022, F-0028, F-0029, F-0030, F-0034, F-0040). F-0047 is
   the only single-attempt one. Three open proposals are merged the same way:
   - F-0088 (awaiting the owner) has func_00060BD0 spliced in without the six declarations its
     own C has (`D_0017FB4C`, `D_000D9443`, `D_000D4CBC`, `func_00060C80`, `func_00010300`, `exit`).
     Its re-gate should fail with E1011, as F-0028's did. This is a prediction and has not been
     compiled.
   - F-0013 (6 functions, 12 attempt directories) looks like the same case: a name scan finds
     `D_001D3738`, `D_001C6F18`, `D_001C6F1C` and `D_00293050` used with no declaration.
   - F-0018 (2 functions): the same scan finds no undeclared name.

   The scan is a heuristic over D_/func_ names (scratchpad script, not committed). It cannot see
   struct-field conflicts such as F-0020's `unk_00C0` or F-0030's `unk_000A`.
   `driver.py:6216` (`--land-held`, a unit's second function) uses the same splice and may lose
   declarations the same way. Not checked.
4. **func_000AB650 needs no rule.** The todo's "never proposed, `flags propose` from their sweep
   hits" is wrong for it: there is no sweep hit, and its C matched under the default. It was
   measured only with func_000AB600 in C before it. An INCLUDE_ASM marker emits no bytes
   (`include/common.h`), so on its own it is the unit's only new C after func_000AB5B0.

### Owner questions

**Q1. u_0005db20 (func_0005DB80, func_0005E500, and func_0005DB20 at 82.67%).** How should F-0029 get a candidate that compiles?
- A. After the drive, write one unit file by hand: HEAD's unit, plus DB80's C from
  20261118-flags a1 `checks/0002.c`, E500's C from nearmiss4-copilot a2 `checks/0005.c` and
  DB20's C from 20261107-030004 a1 `checks/0003.c`, each with its own declarations. Then
  propose it as a new hand proposal and re-gate it under `-4r -oneatx`. F-0029 stays failed as
  its record.
- B. Fix the merge first (Q3), then rebuild F-0029's candidate with the fixed tool and re-gate it.
- C. Land DB80 and E500 under the default with func_0005E550 back in INCLUDE_ASM. This loses a
  matched function, so the gate refuses it.

Recommendation: B, with A as the fallback if Q3 waits. C is not an option.

**Q2. func_000B4B80.** How should it land?
- A. Split u_000b4470 so B4B80 gets its own `-5r -oneatx` unit. This would be the project's first
  `-5r` rule, and finding 2 is evidence against it.
- B. Rule change for the gate: the leading-table span check (07-48b) also accepts ours *longer*
  by alignment filler between the table's end and a 16-aligned head. It would apply only when
  the original span holds no such filler, the head's start is 16-aligned and the extra bytes
  decode as filler. The span is never landed and the whole-EXE SHA-1 still decides. B4B80 then
  lands under the unit's existing rule and F-0072 is rejected. TDD on a relocs/check fixture,
  after the 12 bytes are decoded.
- C. Park it.

Recommendation: B. It is a gate rule, so it is the owner's ruling, as 07-48 option A and 07-48b were.

**Q3. Tooling, main session (todo `flags-merge-keeps-declarations`).** Should `_merge` carry the
hitting file's file-scope declarations that the candidate lacks, and fail the proposal with a
named reason when a struct tag or an extern is declared differently? Recommendation: yes, via
TDD after the drive, before F-0088, F-0013 and F-0018 are re-gated. If it waits, those re-gates
will most likely fail the way F-0028 and F-0029 did.

**Q4. tacp func_000AB650.** Which route gets it a session?
- A. A hand pass after the drive: put the 20261101 AB600 a3 `checks/0002.c` definition of AB650
  (with its externs) into the unit, run one `attempt check` and gate it.
- B. Let `--picks` admit `closure` rows (a `picker.py` change).
- C. Leave it.

Recommendation: A. It is one 31-byte function with C already measured at 100%. B is worth doing
only if more closure rows turn up at 100.

The u_000502b0 pair (func_00050A20, func_00050A80) is not a flags question. F-0071 landed `-ox`
with `-4r -oneatx` as its first alternative, so a sweep with func_000509C0 in C could show
whether `-oneatx` avoids the tail merge. Untested; noted here only so the pair is not lost.

## Q2 done (2026-11-24): the leading-table span accepts our alignment filler (ruling B)

Owner ruling 2026-11-24, Q2: B. The gate change is in `relocs.py` (`_table_surplus`,
`_surplus_reason`, called by `check_function(..., table=True)`) and `check.py`
(`_padded_table`), with tests in `tests/test_check.py` (`test_padded_table_*`, synthetic bytes).

**The 12 bytes, decoded** (our object, `-4r -oneatx`): our `_TEXT` is the 20-byte table
(5 off32 entries) at offset 0, then `lea eax, [eax+0]` and `lea edx, [edx+0]` (disp32 0, 6
bytes each), then func_000B4B80 at offset 0x20. No fixup of ours lies in the 12 bytes. Both are
`x86.is_alignment_filler`. The original's D_000B4B6C runs right up to 0xB4B80.

**The rule.** A leading table's span longer than the original's passes its length rule only when
all of these hold: the original's span is its data-in-code row alone, with no filler after the
table (`_padded_table`); the surplus is at most 15 bytes; the original head and our head are
both 16-aligned; no fixup of ours overlaps the surplus; and the surplus decodes exactly to
alignment filler. The span is then compared over the original's length: equal bytes and every
entry checked against its LE fixup, as before. A shorter span, non-filler bytes, filler past the
16-aligned head, an unaligned head, or a fixup in the surplus are refused, and each refusal is
named.

**Why it cannot land a non-identical function.**
- The rule only covers the table's span. The head function's own check is unchanged: its full
  row, byte-equal, objdiff 100%, every relocation resolved.
- Inside the span, every byte of the original's table is still compared, and reverse coverage
  still requires each original LE fixup to be one of ours. A table of ours with more entries
  would have fixups in the surplus, which is refused (d). One with fewer entries would put filler
  where the original has entries, which fails the byte and fixup checks.
- The surplus is never compared, but it is never landed either: land splices the head's row
  alone (07-48b). The original's table bytes stay, and the whole-EXE SHA-1 still decides.

**e2e (clone container, F-0072's candidate `build/flags/F-0072/u_000b4470.c` under the unit's
own rule `-4r -oneatx`; status.csv written to a scratch config copy only):**
- before: `MISMATCH func_000B4B80 ... reloc FAILED (1)`: `0x000B4B80: length differs: ours 32
  bytes, original 20 bytes; ours is longer than the row`. UFO2P splice MISMATCH, landed 155.
- after: `OK func_000B4B80 0x000B4B80 96 bytes objdiff 100% reloc ok bytes ok`; `splice OK
  UFO2P.EXE sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 landed 156`; TACP unchanged (157).

So func_000B4B80 lands under the unit's existing rule, with no `-5r`. F-0072 can be rejected.
Landing it is still a normal gate run on a committed unit file that holds this C. The owner or
the orchestrator does that; this unit did not.

## Update (2026-11-24): owner rulings and the rebuild

Owner rulings of 2026-11-24: **Q1 B** (fix the merge, rebuild F-0029 with the fixed tool, re-gate
it), **Q2 B** (the gate's leading-table span check; another unit of work), **Q3 yes**, **Q4 A**
(a hand pass, later).

Q3 was already built on 2026-11-20 (b079dac3, todo `flags-merge-keeps-declarations`): `_merge`
carries the hitting file's file-scope items that its definition uses, and fails the proposal
with a named reason when a struct tag, typedef or extern is declared differently on the two
sides; `flags rebuild ID...` remakes a candidate from its evidence. No code change was needed.

`flags rebuild` run on 2026-11-24 in a clone, with the evidence copied from the checkout's
`build/driver/`:
- **F-0029: refused, stays failed.** `20261113-cascade-glm-5.3/.../func_0005DB80/attempt-2/checks/0005.c`
  and the candidate declare `struct unk_007E` differently: DB20's file (20261107-030004 a1
  `checks/0003.c`) has `{ s16 unk_00; u8 pad_02[0x7C]; }` for `D_00128616`, DB80's has
  fields at 0x04 and 0x1C..0x24 for `D_001285E8`. This is the refusal the Q3 ruling asks for, so
  Q1 B ends here and nothing was re-gated. The first hit (20261101-023246 E500 a2 `checks/0002.c`)
  is a stale base as well: its `struct unk_0276` (`unk_000`, `state`, `owner`) differs from the
  committed one, so the R2 splice of matched func_0005E550 at re-gate would refuse it too. No
  rebuild from the queued evidence can compile. A clean set exists only outside the sweep
  evidence: DB80 from 20261118-flags a1 `checks/0002.c` (a sweep hit, 100% under `-4r -oneatx`,
  raw pointers, no struct), E500 from nearmiss4-copilot a2 `checks/0005.c` (a plain check, not a
  sweep, so no tool route takes it; its `unk_0276` equals the committed one) and DB20 as above.
  That is Q1 A. **Owner question:** Q1 A as the fallback (a hand proposal of those three, re-gated
  under `-4r -oneatx`), or park u_0005db20.
- **F-0018: refused, now failed.** `20261119-claude-claude-opus-5-5/.../func_000A5BC0/attempt-1/checks/0001.c`
  and the candidate declare `D_002A18EC` differently (`char` against `unsigned char ...[]`). Before the
  rebuild it was `proposed` with a candidate merged by the old tool. It needs a hand merge.
- **F-0013: rebuilt, proposed.** The candidate gained `D_001C6F18`, `D_001C6F1C`, `D_001D3738`
  and `D_00293050` (the four names its 2026-11-07 re-gate failed on with E1011). Re-gate below.
- F-0088 needed nothing: it landed on 2026-11-20.

Nothing here is approvable yet: F-0029, F-0018 and F-0013 (re-gate below) each wait on an owner answer first.

F-0013 re-gate (container, `flags regate F-0013`, 2026-11-24): **exit 2, failed, compile error**,
no objdiff measured. The R2 splice put in the committed C of func_0007A000, 7A010, 7A040, 7A060,
7A070 and 7A090. Then wcc386 stops at E1062 / E1071 on func_0007A000: the candidate's
func_00079FE0 is its first hit's C (20261031-231600 a1 `checks/0003.c`), which declares
`unsigned char func_0007A000(unsigned char a);` and tail-calls it, while the committed, matched
definition is `void func_0007A000(void)`. The later hit of the same function
(20261119-claude-claude-opus-5-5 a1 `checks/0003.c`) agrees with the committed C, but `_merge` keeps
a function's first hit and records later ones as evidence only. The R2 splice's conflict check
does not compare a candidate's prototype with a spliced definition, so the compiler is what
names the mismatch here. **Owner question (tooling):** should `_merge`/`rebuild` take a function's
latest hit instead of its first (or the first one consistent with the committed C)? Or should
F-0013 go to a hand proposal built on the 20261119 C? Either way, regate it again afterwards.

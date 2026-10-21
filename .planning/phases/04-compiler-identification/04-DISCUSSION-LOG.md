# Phase 4: Compiler identification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-21
**Phase:** 04-compiler-identification
**Areas discussed:** 10.5's damaged compiler, Library match + runtime map, How far 'flags' goes, Compiler wrapper shape

The discussion ran inside plan mode, together with the owner's triage of six Phase 3 leftovers; those choices are logged at the end.

---

## 10.5's damaged compiler

| Option | Description | Selected |
|--------|-------------|----------|
| Own decoder, time-boxed | Write a stdlib wpack decoder called by `install-watcom 10.5`, pin the hash; fall back to deferral after about a day | ✓ |
| One-off manual extraction | Run 10.5's DOS installer once (DOSBox/VM) and pin the hash; not reproducible with our tools | |
| Defer 10.5 | Run 10.6 and 11.0 now; 10.5 only if 10.6 is ambiguous | |

**User's choice:** Own decoder, time-boxed.

| Option | Description | Selected |
|--------|-------------|----------|
| 10.5, 10.6, 11.0 | Exactly CID-01's three; 11.0a/b only if 11.0 is a candidate | ✓ |
| All five installed | Add 11.0a and 11.0b | |
| Add 10.5a too | Apply the c105_a.zip patch as a sixth variant | |

**User's choice:** 10.5, 10.6, 11.0.

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, once per version | Native Windows vs wibo probe object hashes, manual and logged | ✓ |
| No, trust wibo | decomp.me and Theme Hospital already use wibo 1.2.0 | |

**User's choice:** Yes, once per version.

---

## Library match + runtime map

| Option | Description | Selected |
|--------|-------------|----------|
| KKND lib_match + own omf.py | Lift CC0 lib_match.py, add a stdlib OMF reader that Phase 5's omf2elf grows from | ✓ |
| wlib + wdis text compare | No new parser, weaker than a byte match | |
| Port NHL95PC libmatch.py | Licence to check | |

**User's choice:** KKND lib_match + own omf.py.

| Option | Description | Selected |
|--------|-------------|----------|
| All 32-bit LIB386 libs | Includes 3S and 387/emulator variants as flag evidence | ✓ |
| Only CLIB3R + MATH3R | Exactly CID-04's names | |

**User's choice:** All 32-bit LIB386 libs.

| Option | Description | Selected |
|--------|-------------|----------|
| Commit config/<exe>/runtime.csv | Checked artifact; Phase 5 seeds from it; drift test | ✓ |
| Regenerate into build/ only | Gitignored, recomputed | |

**User's choice:** Commit config/<exe>/runtime.csv.

| Option | Description | Selected |
|--------|-------------|----------|
| Per-module versions | Version sets per module; library version reported separately from the compiler version | ✓ |
| Single verdict | Majority version, exceptions in a footnote | |

**User's choice:** Per-module versions.

---

## How far 'flags' goes

| Option | Description | Selected |
|--------|-------------|----------|
| Scan-provable now, rest Phase 5 | Prove -3r/-3s, -s, -fpi, -4/-5, model; -o*/-zp as candidates | ✓ |
| Include a hand-matched probe | Hand-match 2-3 leaf functions now to pin -o*/-zp | |
| Only version, no flags | Move all flags to Phase 5 | |

**User's choice:** Scan-provable now, rest Phase 5.

| Option | Description | Selected |
|--------|-------------|----------|
| Separate evidence per EXE | Full evidence for UFO2P and TACP, one column each | ✓ |
| UFO2P first, TACP spot-check | Cheaper; CID-05 says per EXE | |

**User's choice:** Separate evidence per EXE.

| Option | Description | Selected |
|--------|-------------|----------|
| Idioms + counts, no contradictions | Counts favour one family, nothing contradicts; ties stated | ✓ |
| Exact instruction sequences | Probe bytes must appear verbatim | |

**User's choice:** Idioms + counts, no contradictions.

---

## Compiler wrapper shape

| Option | Description | Selected |
|--------|-------------|----------|
| `reverseapoc cc` | New CLI verb, code in compiler.py | ✓ |
| `reverseapoc compile` | Same, longer name | |
| Standalone tools/wcc.py | Separate script, second entry point | |

**User's choice:** `reverseapoc cc`.

| Option | Description | Selected |
|--------|-------------|----------|
| Glob lines, last match wins | `<glob> <compiler>@<version> <flags...>`, `#` comments, `*` default first | ✓ |
| TOML table | config/cflags.toml with [[rule]] entries | |

**User's choice:** Glob lines, last match wins.

| Option | Description | Selected |
|--------|-------------|----------|
| Refuse + log banner | Hash gate against watcom.toml, banner in the build log | ✓ |
| Warn only | Log and compile anyway | |

**User's choice:** Refuse + log banner.

| Option | Description | Selected |
|--------|-------------|----------|
| Relative backslash paths | decomp.me-style rewrite; refuse spaces and leading `-`; version's own H/ | ✓ |
| You decide | Leave to research/planning | |

**User's choice:** Relative backslash paths.

---

## Claude's Discretion

- Clean-room probe C sources covering mosura's constructs (mosura's licence unverified).
- C vs C++ scan method.
- Module and test layout, CLI verbs other than `cc`, how the wibo spike is recorded.

## Deferred Ideas

- 10.5a and 11.0a/11.0b sweeps (only if needed).
- 10.0a media if the runtime map shows older CRT modules mixed in.
- Confirming -o*/-zp by real matches (Phase 5).

## Phase 3 leftovers triaged in the same session

| Item | Options | Selected |
|------|---------|----------|
| Deferred WR-01/03/08, IN-12 (Phase 5) and WR-04 (Phase 6) | Now, before Phase 4 / Keep deferred / Fold into Phase 4 plans | Now, before Phase 4 |
| GSD merge commits without the Co-Authored-By trailer | Leave history, prevent with a tracked commit-msg hook / Leave as-is / Rewrite history | Leave history, prevent |
| Ledger only keeps CR/BL/WR/IN ids | Document the convention / Document + upstream issue / Patch local GSD | Document the convention |
| Plan Phase 4 in this session or a new one | (owner comment on the plan) | This session, after the leftovers are fixed |

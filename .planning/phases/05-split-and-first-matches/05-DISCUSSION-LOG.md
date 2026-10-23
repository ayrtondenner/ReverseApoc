# Phase 5: Split and first matches - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-23
**Phase:** 05-split-and-first-matches
**Areas discussed:** Spike, Ghidra and fallback; Function list reconciliation; Units and stub convention; First matches and compiler sweep

Facts checked during the session (read-only):
- WSL2 `ubuntu-recovered` had no Java and no Ghidra.
- JDK 21.0.12.1 runs on the Windows host.
- The Ghidra 12.2 and 12.1.4 zips' SHA-256s match their release notes.
- The lastonesky loader ships only a v12.1.4-1 asset (digest `0a9c65ce…be45`).
- retrokit compiles its loader against any Ghidra 12.x.
- capstone 5.0.9 ships py3-none wheels.

---

## Spike, Ghidra and fallback

### Spike timing

| Option | Description | Selected |
|--------|-------------|----------|
| First, time-boxed | Wave 1, about 1 day, on a known-good Phase 4 runtime function with a minimal omf2elf | ✓ |
| After omf2elf is complete | Full omf2elf with tests first, then the spike | |
| You decide | | |

### INVALIDATED criterion

| Option | Description | Selected |
|--------|-------------|----------|
| objdiff can't reach 100% | Fall back only if objdiff cannot load our ELF or cannot show 100% on a byte-identical pair; workarounds mean PARTIAL | ✓ |
| Any workaround means fallback | Stricter | |
| Never fall back in Phase 5 | Fix omf2elf until it works | |

### LE loader (first round)

| Option | Description | Selected |
|--------|-------------|----------|
| lastonesky ghidra-lx-loader | v12.1.4-1, Watcom cspec, no export | ✓ (first round) |
| retrokit | Own loader, export, MCP; sizes need an adapter | |
| Try both, keep one | About half a day more | |

### Ghidra environment (first round)

| Option | Description | Selected |
|--------|-------------|----------|
| Script + you run it | Pinned install script in WSL2 | |
| Claude installs it in-session | | |
| Already have / will do by hand | | |

**User's choice:** Free text. They had installed JDK 21.0.12.1 on Windows and downloaded Ghidra 12.2, and asked for it to be unpacked into a gitignored folder in the repo.

### LE loader (second round, after finding lastonesky ships no 12.2 build)

| Option | Description | Selected |
|--------|-------------|----------|
| retrokit on Ghidra 12.2 | javac-compiled loader works on any 12.x | |
| lastonesky rebuilt for 12.2 | Gradle rebuild | |
| lastonesky on Ghidra 12.1.4 | A second download | |

**User's choice:** Free text. They downloaded Ghidra 12.1.4 (`ghidra_12.1.4_PUBLIC_20260921.zip`), keeping lastonesky, and asked for a script so other developers get it downloaded automatically.

### Ghidra location (third round)

| Option | Description | Selected |
|--------|-------------|----------|
| third_party/ghidra/12.1.4/, Windows host | Native analyzeHeadless.bat with the owner's JDK | ✓ (later superseded) |
| Same folder, run from WSL2 | Second JDK in WSL2 | |

### Download script shape

| Option | Description | Selected |
|--------|-------------|----------|
| fetch/install/check-ghidra verbs | Same as watcom.py, with config/ghidra.toml | ✓ (later superseded) |
| One standalone shell script | | |

### Unpack timing

| Option | Description | Selected |
|--------|-------------|----------|
| First executed task | Scripted, hash-checked | ✓ |
| Right after this discussion | Manual | |

### Plan review: why not put JDK and Ghidra in the Dockerfile?

At plan review the owner asked why the Docker image couldn't already carry the JDK and Ghidra. Claude's answer:
- The user-supplied rule covers only Watcom and the game. Ghidra is Apache-2.0 and OpenJDK is GPLv2+CE.
- The earlier WSL2 choice was about image weight (STACK.md: "about 540 MB plus JDK, unrelated to the compile oracle").

The owner then asked whether the JDK was only for the GUI. Claude clarified that Ghidra itself runs on Java, so headless use needs a JDK too, and a Linux container cannot use the Windows JDK.

| Option | Description | Selected |
|--------|-------------|----------|
| Main image + headless JDK | openjdk-21-jdk-headless + Ghidra 12.1.4 + loader, SHA-pinned, about +800 MB | ✓ |
| Separate compose service | Same contents, own image | |
| Host install (previous plan) | third_party/ghidra + fetch verbs | |

**Notes:** This supersedes the host location and the fetch/install/check-ghidra verbs. The owner's Windows JDK stays optional, for a host GUI.

---

## Function list reconciliation

| Option | Description | Selected |
|--------|-------------|----------|
| LE evidence rule | Starts backed by call/fixup/entry/runtime evidence; neither tool wins by default | ✓ |
| Ghidra wins | | |
| capstone wins | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Zero unexplained, all recorded | Committed boundaries.csv with a verdict per disagreement, enforced by a test | ✓ |
| Only around matched functions | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Runtime dep, pinned | capstone==5.0.9 in dependencies + uv.lock | ✓ |
| Optional extra | | |
| No capstone, own decoder | | |

| Option | Description | Selected |
|--------|-------------|----------|
| start,end,name,kind,unit,evidence | No status column; the Phase 6 status table owns status | ✓ |
| Add a status column | | |
| You decide | | |

---

## Units and stub convention

| Option | Description | Selected |
|--------|-------------|----------|
| Evidence-based draft for the whole EXE | Every function in one unit; only first-match units must be right | ✓ |
| One function per unit for now | | |
| Only the units we touch | | |

| Option | Description | Selected |
|--------|-------------|----------|
| INCLUDE_ASM marker, no code | KKND-style extern marker; the splice keeps original bytes | ✓ |
| Unit files list only matched C | | |
| GNU-asm INCLUDE_ASM | | |

| Option | Description | Selected |
|--------|-------------|----------|
| One ELF per unit, written by Python | Symbols per function, relocations from LE fixups | ✓ |
| One ELF per function | | |

| Option | Description | Selected |
|--------|-------------|----------|
| include/watcom_compat.h, __WATCOMC__=1060 | clang 18 pinned into the image | ✓ |
| You decide | | |

---

## First matches and compiler sweep

| Option | Description | Selected |
|--------|-------------|----------|
| P16 filter, separate per EXE | Easiest-first scorer | ✓ |
| Prefer a UFO2P/TACP twin | | |
| Library function first, then game | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Claude, oracle decides | The owner reviews the C at UAT | ✓ |
| You write it, Claude builds tools | | |
| Pair: checkpoint per function | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Bounded matrix, then next candidate | 3 versions × 2 CPU × 5 -o, up to 3 candidates per EXE | ✓ |
| Open-ended per function | | |
| Wider matrix incl. -zp/-zm/-fp | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Per-glob rule now, default needs 3+ | Ties stay ties | ✓ |
| First match sets the default | | |
| Never change the default in Phase 5 | | |

---

## Closing

| Option | Description | Selected |
|--------|-------------|----------|
| Ready for context | The check tool UX and execution topology are left to the planner | ✓ |
| Discuss execution topology | | |
| Discuss the check tool UX | | |

## Claude's Discretion

- The output, `--json` shape and exit codes of `reverseapoc check`.
- omf2elf internals.
- Scorer details.
- The Ghidra script language.
- The straddling-fixup and negative tests.
- Execution topology (the Phase 4 pattern).
- Correcting the docs that still say WSL2 for Ghidra.

## Deferred Ideas

- decomp.wtf INCLUDE_ASM acceptance (Phase 6 spike).
- Sweeps of `-zp*`, `-zm` and `-fp3/5`.
- 11.0a/11.0b.
- Installed vs CD build.
- GhidraMCP / retrokit MCP.
- A host Ghidra GUI guide.

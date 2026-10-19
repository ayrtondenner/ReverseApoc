# Coding style

Rules for the decompiled C under `src/` and `include/`. Python tooling under `tools/` follows ruff's defaults and is tested with pytest; it is not covered here.

The order of authority: **the binary first, readability second.** When a style rule and the original codegen disagree, the codegen wins and a comment explains why.

## Language: C89 for Watcom 10.x

The game is C compiled with `wcc386` (see [toolchain.md](toolchain.md#c-not-c)). Watcom 10.x's C front end is C89/ANSI C:

- Declare every local at the start of its block, before any statement. No mixed declarations and code, no `for (int i = 0; ...)`.
- Use `/* */` comments only. Watcom accepts `//` as an extension; we stay strict.
- No variable-length arrays, no `inline`, no `bool`, no designated initializers, no compound literals.
- **Never reorder declarations** in a matched function. Order decides stack slots and the layout of statics (Theme Hospital's rule).
- Mid-block declarations are the most common AI mistake on C89 targets (Macabeus, Lewis). The lint gate below catches them.

If a module turns out to be C++, it is compiled with `wpp386` per file and gets its own rules then.

## Watcom specifics

- **Calling convention.** The default is Watcom's register convention (`__watcall`): arguments in `eax`, `edx`, `ebx`, `ecx`, then the stack. C function symbols get a trailing underscore (`name_`) and data symbols a leading one (`_name`).
- **`#pragma aux`** declares calling conventions, register parameters, return registers and clobbered registers for a function. Put pragmas in headers next to the prototype. Pragma bodies that emit code bytes are not allowed in `src/` (see [workflow.md](workflow.md#hooks-guardrails-phase-6)).
- **`__near` / `__far`**: the program is flat 32-bit, so expect them only around DOS/4GW, interrupt or real-mode interfaces. Keep them where the original needs them.
- **Struct packing** is set with `-zp` (`-zp1` in KKND and NHL95PC). Ours is TBD, recorded in [matching.md](matching.md) in Phase 4. Struct layouts and offset comments must follow it.
- **Enums** take the smallest signed type that fits under Watcom; a field that holds an enum value keeps its original integer type.
- **Compat header.** clang and clangd do not understand Watcom keywords. A compat header defines `__far`, `__near`, `__interrupt`, `__cdecl` and `__watcall` as empty for clang only, alongside `-D__386__ -D__FLAT__` and a `__WATCOMC__` value (TBD, set to match the version found in Phase 4). Its path is decided in Phase 5.

## Naming

Recovered names should be meaningful, but a placeholder is better than a guess.

| Kind | Until named | Once named |
|---|---|---|
| Function | `func_XXXXXXXX` (linear address at the preferred base, 8 hex digits) | lowercase `snake_case` with a module prefix, e.g. `research_start_project` |
| Global data | `D_XXXXXXXX` | lowercase `snake_case` with a module prefix |
| Struct | `struct unk_XXXX` (size in hex) | tag `name_s`, typedef `name_t` |
| Scalar typedef | n/a | `name_t` |
| Constant, macro, enumerator | raw literal | `ALL_CAPS` |
| Boolean-returning function | n/a | `is_`, `has_`, `can_` prefix |

- Addresses are linear addresses in that EXE at its preferred bases (code 0x10000, data 0xD0000 or 0xE0000), so they line up with Ghidra and with OpenApoc's notes. UFO2P and TACP share address ranges, so sources live per EXE (`src/ufo2p/`, `src/tacp/`, shared code in `src/common/`).
- Keep original names where the binary reveals them: source file names such as `grafix.c` and `pixlpath.c`, and names in diagnostic strings.
- Prefer OpenApoc's names for concepts it already models, and cite where a name came from in a comment when it is not obvious.
- Units in names when it helps: `delay_ticks`, `cost_credits`.

## Comments for OpenApoc readers

Comments are the main way this project helps OpenApoc. Write them for a developer who knows the game but not x86.

- Above each function: one or two sentences on what it does in game terms, then inputs, outputs and the globals it reads or changes.
- Mark behaviour of the original that looks wrong with `BUG(original):` and describe the effect in game terms. Never fix it in matched code; fixing changes the bytes.
- Mark shapes that exist only to reproduce the original codegen with `NOTE(match):`, so nobody "cleans them up" later.
- Struct fields get offset comments, and structs a size comment: `/* 0x08 */ int32_t speed;` and `} vehicle_t; /* size: 0x18 */`. Offsets must respect the `-zp` packing (Kappa's offset-comment idea, with Watcom alignment instead of its hard-coded 8).
- Keep comments short and lead with what matters (the i-have-adhd spirit, see [ceremonies.md](ceremonies.md#i-have-adhd)).

## What conflicts with "match the original"

Common advice that we reject for matched code, and why:

| Advice | Source | Why it conflicts |
|---|---|---|
| Declare variables in the narrowest scope and initialize them at declaration | Google C++ Style Guide | C89 needs block-top declarations, and declaration order decides stack slots |
| `modernize-*` and `cppcoreguidelines-*` checks | clang-tidy | They propose C++11 rewrites that cannot compile under `wcc386` or change codegen |
| Smart pointers, RAII, STL, concepts, ranges, replacing C arrays and `NULL` | cpp-pro, Mindrally cpp | Modern C++ idioms; the target is 1997 C |
| `-Wconversion`-driven explicit casts and fixed-width types everywhere | OpenSSF hardening, general advice | Casts and type changes alter integer promotion and the instructions emitted |
| Adding `const` or `static`, reordering headers or includes | general advice | Can change symbol layout, data placement and include-dependent code |
| Bounds checks and fixing original bugs | SEI CERT C, general advice | Changes the code; document with `BUG(original):` instead |
| Replacing magic numbers with enums everywhere | general advice | Fine only where the type stays the same (Theme Hospital: enumerators replace literals only) |
| Extracting helpers, de-duplicating, flattening control flow | Ponytail, `/simplify`, thermo-nuclear review | Any shape change alters codegen |

These rules still apply to new, non-matching code such as test harnesses and the compat header.

## Lint gate

- **Dialect:** `clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement` with the compat header, over every C file, in CI and before a match is committed. clang-tidy has no dedicated check for this.
- **Formatting:** clang-format with pragma masking, proven build-neutral (see [ceremonies.md](ceremonies.md#clang-format-on-c)).
- **Optional:** an ast-grep rule for declarations after statements, and ast-grep recipes for structural search across `src/`.

## Standards consulted

| Standard | What we take |
|---|---|
| [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html) | Header guard form and self-contained headers; its scoping rules are rejected for matched code |
| [C++ Best Practices](https://github.com/cpp-best-practices/cppbestpractices) | "Use the tools available": lint and format in CI. Only the chapter list was reviewed; contents TBD |
| [micro-os-plus naming conventions](https://micro-os-plus.github.io/develop/naming-conventions/) | `snake_case`, `_t` typedefs, `_s` struct tags, `is_`/`has_` booleans, units in names |
| [Imperial College C Style](https://www.doc.ic.ac.uk/lab/cplus/cstyle.html) | Always brace bodies, `ALL_CAPS` macros and constants, module prefixes for globals, parenthesized macro parameters, comment fall-through. Applied where the binary allows |
| [OpenSSF Compiler Hardening Guide](https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html) | Host-side tooling only (any C built with gcc or clang for tests); never the Watcom matching build |
| [SEI CERT C](https://cmu-sei.github.io/secure-coding-standards/sei-cert-c-coding-standard/) | Sections INT, ARR, STR, MEM and EXP as lenses for spotting and documenting original bugs (overflow, bounds, termination, allocation, evaluation order), not for rewriting |
| [oodlescoop C best practices](https://www.oodlescoop.com/tutorials/c-programming/best-practices-and-coding-standards-for-c-programming) | TBD: listed in the kickoff, but the research could not locate its content |

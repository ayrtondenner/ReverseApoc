---
paths:
  - "src/**"
  - "include/**"
---
# Decompiled C (matched source)

- Target compiler is Watcom C 10.x (C89). Declarations only at block start, `/* */` comments,
  no `//`, no mixed declarations and code, no VLAs, no `inline`, no C99 or C++ features.
- A matched function is byte-identical to the original. Never restructure, simplify, reorder
  declarations, or "modernize" a function that already matches: any shape change alters codegen.
- Allowed edits to matched code: renaming identifiers, comments, struct/field names in headers
  that do not change layout or packing (`-zp`), and documentation of original bugs as
  `/* BUG(original): ... */`.
- Never write inline assembly or `#pragma aux` to force a match; a function that cannot be
  matched in C stays an `INCLUDE_ASM` stub.
- Never touch `orig/`, hash manifests under `config/`, or build scripts to make a check pass.
- Lint gate: `clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement` with the
  compat header. clang-format only with pragma masking; formatting must never change the build.

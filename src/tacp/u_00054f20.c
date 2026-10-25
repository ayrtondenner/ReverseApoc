/*
 * src/tacp/u_00054f20.c: translation unit u_00054f20 of TACP.EXE, 0x00054F20..0x00056D70 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00054f20`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00054F20);
INCLUDE_ASM(func_000550C0);
INCLUDE_ASM(func_00056070);
INCLUDE_ASM(func_000560E0);
INCLUDE_ASM(func_000562B0);
INCLUDE_ASM(func_00056590);
INCLUDE_ASM(func_00056940);
INCLUDE_ASM(func_00056A10);
INCLUDE_ASM(func_00056BB0);
INCLUDE_ASM(func_00056D20);

int func_00011500(void);

extern int D_0028DF70;

/*
 * func_00055080: calls func_00011500 and stores its result in D_0028DF70. Neither name is
 * known yet.
 *
 * Declared void because the body only stores: wcc386 gives the same 11 bytes for
 * `void f(void) { D = g(); }` and `int f(void) { return D = g(); }`, so the bytes cannot
 * tell them apart. It stays void until a caller that reads EAX after the call shows
 * otherwise (docs/learnings.md, 2026-10-24, the first TACP match).
 */
void func_00055080(void)
{
    D_0028DF70 = func_00011500();
}

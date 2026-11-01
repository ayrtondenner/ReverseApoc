/*
 * src/tacp/u_000443f0.c: translation unit u_000443f0 of TACP.EXE, 0x000443F0..0x00044DF0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000443f0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00044440);
INCLUDE_ASM(func_000445D0);
INCLUDE_ASM(func_00044950);
INCLUDE_ASM(func_00044B10);
INCLUDE_ASM(func_00044C90);

/* (address, old value) pairs of s32; D_000E6D00 points one past the top pair. */
extern s32 *D_000E6D00;

/* void: EAX holds a scratch pointer at ret. */
void func_000443F0(void)
{
    s32 *q;
    s32 *p;

    q = D_000E6D00 - 2;
    p = q;
    while (q[0] != 0) {
        *(s32 *)p[0] = p[1];
        q = p - 2;
        p = q;
    }
    q = p + 2;
    D_000E6D00 = q;
}

/*
 * src/tacp/u_0009b0e0.c: translation unit u_0009b0e0 of TACP.EXE, 0x0009B0E0..0x0009C350 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0009b0e0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0009B0E0);
INCLUDE_ASM(func_0009B140);
INCLUDE_ASM(func_0009B9E0);
INCLUDE_ASM(func_0009BCA0);
INCLUDE_ASM(func_0009BD70);
struct unk_0046 {
    /* 0x00 */ u8 pad_00[0x45];
    /* 0x45 */ u8 kind;
}; /* size: not read (only the field at 0x45 is used) */

int func_0009BE20(struct unk_0046 *p)
{
    switch (p->kind) {
    case 0:
        return 5;
    case 1:
        return 5;
    case 2:
        return 6;
    default:
        return 0;
    }
}

INCLUDE_ASM(func_0009BE50);

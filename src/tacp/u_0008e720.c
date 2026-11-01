/*
 * src/tacp/u_0008e720.c: translation unit u_0008e720 of TACP.EXE, 0x0008E720..0x00090990 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0008e720`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0008E770);
INCLUDE_ASM(func_0008F2F0);
INCLUDE_ASM(func_0008F3F0);
INCLUDE_ASM(func_0008F7F0);
INCLUDE_ASM(func_0008FB80);
INCLUDE_ASM(func_00090960);

struct unk_02BD {
    /* 0x000 */ u8 pad_000[0x2BC];
    /* 0x2BC */ u8 flags;
}; /* size: at least 0x2BD */

int func_00090940(struct unk_02BD *a, struct unk_02BD *b)
{
    int x;

    x = (u8)(a->flags ^ 4);
    return (x | (u8)(b->flags ^ 4)) ^ 4;
}

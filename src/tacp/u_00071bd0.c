/*
 * src/tacp/u_00071bd0.c: translation unit u_00071bd0 of TACP.EXE, 0x00071BD0..0x00071F50 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00071bd0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00071BD0);
INCLUDE_ASM(func_00071C20);
INCLUDE_ASM(func_00071CA0);
INCLUDE_ASM(func_00071D10);
INCLUDE_ASM(func_00071DB0);
INCLUDE_ASM(func_00071EA0);

struct unk_0018 {
    /* 0x00 */ u8 pad_00[0x12];
    /* 0x12 */ u16 f12;
    /* 0x14 */ u8 pad_14[2];
    /* 0x16 */ s8 f16;
    /* 0x17 */ u8 pad_17[1];
}; /* size: 0x18 */

extern struct unk_0018 **D_002E47E4;
void func_000711C0(u16 arg);

/* Returns 0 when D[index] has type 3 (after calling func_000711C0), 9 otherwise. */
int func_00071CE0(int index)
{
    struct unk_0018 *p;

    p = D_002E47E4[index];
    if (p->f16 == 3) {
        func_000711C0(p->f12 & 0xffff);
        return 0;
    }
    return 9;
}

/*
 * src/ufo2p/u_00063480.c: translation unit u_00063480 of UFO2P.EXE, 0x00063480..0x00063B90 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00063480`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00063480);
INCLUDE_ASM(func_00063530);
INCLUDE_ASM(func_000636D0);
INCLUDE_ASM(func_00063800);
INCLUDE_ASM(func_00063970);
INCLUDE_ASM(func_00063A10);

struct unk_0006 {
    /* 0x00 */ s16 pad_00;
    /* 0x02 */ s16 x;
    /* 0x04 */ s16 y;
}; /* size: not known, 0x06 read here */

struct unk_0276 {
    /* 0x000 */ s16 pad_000;
    /* 0x002 */ s16 kind;
    /* 0x004 */ u8 pad_004[0x110];
    /* 0x114 */ s16 x;
    /* 0x116 */ s16 y;
    /* 0x118 */ u8 pad_118[0x159];
    /* 0x271 */ u8 active;
    /* 0x272 */ u8 pad_272[4];
}; /* size: 0x276 */

extern struct unk_0276 D_00160FD8[];

int func_000634D0(struct unk_0006 *a)
{
    struct unk_0276 *p;
    int found;
    int i;

    p = D_00160FD8;
    found = 0;
    for (i = 0; i < 0x50; i++, p++) {
        if (p->kind != 1 || p->active == 0 || p->x != a->x || p->y != a->y) {
            continue;
        }
        found = 1;
        break;
    }
    return found;
}

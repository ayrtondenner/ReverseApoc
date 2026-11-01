/*
 * src/tacp/u_00074420.c: translation unit u_00074420 of TACP.EXE, 0x00074420..0x00074530 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00074420`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00074420);

struct unk_0088 {
    /* 0x00 */ s16 unk_00;
    /* 0x02 */ s16 min_x;
    /* 0x04 */ s16 min_y;
    /* 0x06 */ s16 min_z;
    /* 0x08 */ s16 max_x;
    /* 0x0A */ s16 max_y;
    /* 0x0C */ s16 max_z;
    /* 0x0E */ u8 unk_0E[0x7A];
}; /* size: 0x88 */

extern struct unk_0088 D_00136148[];

int func_000744E0(s16 x, s16 y, s16 z, s16 idx)
{
    struct unk_0088 *p;
    int r;

    r = 0;
    p = &D_00136148[idx];
    if (x >= p->min_x && x <= p->max_x && y >= p->min_y && y <= p->max_y
        && z >= p->min_z && z <= p->max_z) {
        r = 1;
    }
    return r;
}

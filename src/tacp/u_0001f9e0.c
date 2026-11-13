/*
 * src/tacp/u_0001f9e0.c: translation unit u_0001f9e0 of TACP.EXE, 0x0001F9E0..0x00021A90 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0001f9e0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0001F9E0);
INCLUDE_ASM(func_00020420);
INCLUDE_ASM(func_00021180);

/* 14-byte record of D_00127D90; the first word is 0 when the slot is free. */
struct unk_000E {
    /* 0x00 */ s16 used;
    /* 0x02 */ u8 data[0x0C];
}; /* size: 0x0E */

extern struct unk_000E D_00127D90[];

struct unk_000E *func_00021370(void)
{
    struct unk_000E *p;
    s16 i;

    p = D_00127D90;
    i = 0;
    do {
        if (p->used == 0) {
            break;
        }
        i++;
        p++;
    } while (i < 0x960);
    if (i == 0x960) {
        p = 0;
    }
    return p;
}

INCLUDE_ASM(func_000213A0);
INCLUDE_ASM(func_00021410);
INCLUDE_ASM(func_00021440);
INCLUDE_ASM(func_000214E0);
INCLUDE_ASM(func_000217E0);

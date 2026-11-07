/*
 * src/ufo2p/u_0002f220.c: translation unit u_0002f220 of UFO2P.EXE, 0x0002F220..0x0002F460 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0002f220`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0002F250);
INCLUDE_ASM(func_0002F3C0);

struct unk_002E {
    /* 0x00 */ u8 pad_00[0x0C];
    /* 0x0C */ s32 field_0C;
    /* 0x10 */ u8 pad_10[0x1E];
}; /* size: 0x2E */

extern struct unk_002E D_00170CD0[];
extern struct unk_002E D_00170E9C[];
extern int D_00170EA8;

void func_0002F220(int a)
{
    struct unk_002E *p;
    int zero;

    zero ^= zero;
    p = D_00170CD0;
    D_00170EA8 = zero;
    if (p < D_00170E9C) {
        do {
            p++;
            p[-1].field_0C = 0;
        } while (p < D_00170E9C);
    }
}

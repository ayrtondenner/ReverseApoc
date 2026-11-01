/*
 * src/ufo2p/u_00071740.c: translation unit u_00071740 of UFO2P.EXE, 0x00071740..0x00072DF0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00071740`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00071740);
INCLUDE_ASM(func_00071900);
INCLUDE_ASM(func_00071940);
INCLUDE_ASM(func_00071990);
INCLUDE_ASM(func_00071AF0);
INCLUDE_ASM(func_00071CB0);
INCLUDE_ASM(func_00071CE0);
INCLUDE_ASM(func_00071E80);
INCLUDE_ASM(func_000720F0);
INCLUDE_ASM(func_00072360);
INCLUDE_ASM(func_000724B0);
INCLUDE_ASM(func_00072850);
INCLUDE_ASM(func_00072AA0);
INCLUDE_ASM(func_00072DB0);

/* 20 records of 0x10 bytes: a dword at 0x0016EF42 and a byte at 0x0016EF46 each. */
extern u8 D_0016EF46[];
extern s32 D_0016EF42[];

void func_00072D80(void)
{
    s16 i;

    i = 0;
    do {
        D_0016EF46[i * 16] = 0;
        D_0016EF42[i * 4] = 0;
        i++;
    } while (i < 20);
}

/*
 * src/ufo2p/u_00089240.c: translation unit u_00089240 of UFO2P.EXE, 0x00089240..0x00089980 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00089240`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00089240);
INCLUDE_ASM(func_00089360);
INCLUDE_ASM(func_00089910);
INCLUDE_ASM(func_00089920);
extern short D_001A714C;

/* void: EAX is not set before ret */
void func_00089930(void)
{
    D_001A714C = 3;
}

/* defined right after func_00089930 so wcc386 emits the lea filler that ends its row */
void func_00089940(void)
{
    D_001A714C = 4;
}

void func_00089950(void)
{
    D_001A714C = 5;
}

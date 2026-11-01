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
void state_code_set_3(void)
{
    D_001A714C = 3;
}

/* defined right after state_code_set_3 so wcc386 emits the lea filler that ends its row */
void state_code_set_4(void)
{
    D_001A714C = 4;
}

void state_code_set_5(void)
{
    D_001A714C = 5;
}

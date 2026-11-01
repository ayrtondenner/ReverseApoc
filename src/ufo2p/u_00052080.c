/*
 * src/ufo2p/u_00052080.c: translation unit u_00052080 of UFO2P.EXE, 0x00052080..0x00053660 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00052080`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000520A0);
INCLUDE_ASM(func_000520C0);
INCLUDE_ASM(func_000520E0);
INCLUDE_ASM(func_00052100);
INCLUDE_ASM(func_00052150);

extern int D_000E12F0;
extern short D_00183A80;
extern short D_00183A78;

void button_group_select_1(void)
{
    D_000E12F0 = 1;
    D_00183A80 = 1;
    D_00183A78 = 1;
}

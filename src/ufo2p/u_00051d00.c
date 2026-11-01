/*
 * src/ufo2p/u_00051d00.c: translation unit u_00051d00 of UFO2P.EXE, 0x00051D00..0x00051E60 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00051d00`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00051D00);
INCLUDE_ASM(func_00051D40);
INCLUDE_ASM(func_00051D80);
INCLUDE_ASM(func_00051DA0);
INCLUDE_ASM(func_00051DD0);

extern int D_000D5058;
extern short D_00183A78;
extern short D_00183A80;

void flags_set_d5058_and_pair(void)
{
    D_000D5058 = 1;
    D_00183A78 = 1;
    D_00183A80 = 1;
}

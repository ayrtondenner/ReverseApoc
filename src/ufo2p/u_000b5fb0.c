/*
 * src/ufo2p/u_000b5fb0.c: translation unit u_000b5fb0 of UFO2P.EXE, 0x000B5FB0..0x000B63C0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000b5fb0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000B5FB0);
INCLUDE_ASM(func_000B5FD0);

extern int D_00135818;

void level_update_disable(void)
{
    D_00135818 = 0;
}

/*
 * src/ufo2p/u_000b3400.c: translation unit u_000b3400 of UFO2P.EXE, 0x000B3400..0x000B3AE0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000b3400`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000B3400);

int func_000B3480(int r_eax, int r_edx)
{
    return ((*(unsigned char *)((char *)r_edx + 1)) & 255) - ((*(unsigned char *)((char *)r_eax + 1)) & 255);
}

INCLUDE_ASM(func_000B34A0);

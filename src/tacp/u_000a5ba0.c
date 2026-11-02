/*
 * src/tacp/u_000a5ba0.c: translation unit u_000a5ba0 of TACP.EXE, 0x000A5BA0..0x000A5C10 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000a5ba0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"


extern char D_002A18EC[];
extern char D_002A186C[];

int func_000A5BA0(int r_eax)
{
    *(signed char *)((D_002A18EC + r_eax)) = 0;
    return (*(unsigned char *)((D_002A186C + r_eax))) & 255;
}

INCLUDE_ASM(func_000A5BC0);
INCLUDE_ASM(func_000A5BE0);

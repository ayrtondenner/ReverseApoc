/*
 * src/tacp/u_00079c40.c: translation unit u_00079c40 of TACP.EXE, 0x00079C40..0x00079E00 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00079c40`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00079C60);
INCLUDE_ASM(func_00079C70);
INCLUDE_ASM(func_00079C80);
INCLUDE_ASM(func_00079CF0);

extern int D_0029304C;
extern unsigned char D_000FF2DB[];

unsigned char func_00079C40(int i)
{
    return D_000FF2DB[i * 0x56 + D_0029304C];
}

extern unsigned char D_000F9CDB[];

unsigned char func_00079C50(int i)
{
    return D_000F9CDB[i * 0x56 + D_0029304C];
}

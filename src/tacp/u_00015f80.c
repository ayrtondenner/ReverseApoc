/*
 * src/tacp/u_00015f80.c: translation unit u_00015f80 of TACP.EXE, 0x00015F80..0x00016EF0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00015f80`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

extern char D_000E4D76[];
extern char D_000E4D74[];
extern char D_000E4D7A[];
extern char D_000E4D78[];
int func_00016820(void);

int func_00015F80(void)
{
    int r_eax;

    *(short *)((D_000E4D76)) = 0;
    *(short *)((D_000E4D74)) = 0;
    *(short *)((D_000E4D7A)) = 352;
    *(short *)((D_000E4D78)) = 640;
    r_eax = func_00016820();
    return r_eax;
}

INCLUDE_ASM(func_00015FC0);
INCLUDE_ASM(func_000161B0);
INCLUDE_ASM(func_00016820);

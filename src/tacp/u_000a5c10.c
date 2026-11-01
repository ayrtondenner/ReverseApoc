/*
 * src/tacp/u_000a5c10.c: translation unit u_000a5c10 of TACP.EXE, 0x000A5C10..0x000A6040 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000a5c10`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000A5C10);
INCLUDE_ASM(func_000A5CB0);
INCLUDE_ASM(func_000A5CD0);
INCLUDE_ASM(func_000A5D40);
INCLUDE_ASM(func_000A5D70);
INCLUDE_ASM(func_000A5DA0);
INCLUDE_ASM(func_000A5DB0);
INCLUDE_ASM(func_000A5F90);

extern char D_000E3660[];
int func_000A5CD0(int);
int func_000A5BA0(int);
int func_00021180(void);
extern char D_000E6CC0[];
extern char D_00284CEE[];

void func_000A6000(void)
{
    int r_eax;

    r_eax = func_000A5CD0((int)D_000E3660);
    r_eax = func_000A5BA0((signed char)r_eax);
    if (r_eax != 0) goto LA603D;
    r_eax = func_00021180();
    if (r_eax == 0) goto LA602A;
    *(signed char *)((char *)r_eax + 4) = 14;
    *(short *)((char *)r_eax + 18) = 0;
LA602A:;
    *(short *)((D_000E6CC0)) = 1;
    *(short *)((D_00284CEE)) = 1;
LA603D:;
    return;
}


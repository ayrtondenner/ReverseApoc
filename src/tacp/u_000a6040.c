/*
 * src/tacp/u_000a6040.c: translation unit u_000a6040 of TACP.EXE, 0x000A6040..0x000A6080 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000a6040`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"


extern char D_000E3660[];
int func_000A5CD0(int);
int func_000A5BA0(int);
int func_00021180(void);
extern char D_00284CEE[];
extern char D_000E6CC0[];

void func_000A6040(void)
{
    int r_eax;

    r_eax = func_000A5CD0((int)D_000E3660);
    r_eax = func_000A5BA0((signed char)r_eax);
    if (r_eax != 0) goto LA607D;
    r_eax = func_00021180();
    if (r_eax == 0) goto LA606A;
    *(signed char *)((char *)r_eax + 4) = 14;
    *(short *)((char *)r_eax + 18) = 1;
LA606A:;
    *(short *)((D_00284CEE)) = 1;
    *(short *)((D_000E6CC0)) = 1;
LA607D:;
    return;
}

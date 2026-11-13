/*
 * src/tacp/u_000a60c0.c: translation unit u_000a60c0 of TACP.EXE, 0x000A60C0..0x000A6100 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000a60c0`, which never
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

void func_000A60C0(void)
{
    int r_eax;

    r_eax = func_000A5CD0((int)D_000E3660);
    r_eax = func_000A5BA0((signed char)r_eax);
    if (r_eax != 0) goto LA60FD;
    r_eax = func_00021180();
    if (r_eax == 0) goto LA60EA;
    *(signed char *)((char *)r_eax + 4) = 14;
    *(short *)((char *)r_eax + 18) = 4;
LA60EA:;
    *(short *)((D_00284CEE)) = 1;
    *(short *)((D_000E6CC0)) = 1;
LA60FD:;
    return;
}

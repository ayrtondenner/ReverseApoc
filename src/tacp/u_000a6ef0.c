/*
 * src/tacp/u_000a6ef0.c: translation unit u_000a6ef0 of TACP.EXE, 0x000A6EF0..0x000A87C0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000a6ef0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000A6EF0);
INCLUDE_ASM(func_000A6F20);

extern char D_001EBDE0[];

void func_000A6FD0(void)
{
    *(signed char *)((D_001EBDE0)) = 1;
    return;
}


extern char D_001EBDE2[];

void func_000A6FE0(void)
{
    *(signed char *)((D_001EBDE2)) = 1;
    return;
}


extern char D_001EBDE1[];

void func_000A6FF0(void)
{
    *(signed char *)((D_001EBDE1)) = 1;
    return;
}

INCLUDE_ASM(func_000A7000);

int func_00041140(int);

int func_000A71A0(void)
{
    return func_00041140(0);
}

INCLUDE_ASM(func_000A71B0);
INCLUDE_ASM(func_000A71C0);
INCLUDE_ASM(func_000A71D0);
INCLUDE_ASM(func_000A71E0);
INCLUDE_ASM(func_000A71F0);
INCLUDE_ASM(func_000A7200);
INCLUDE_ASM(func_000A72F0);
INCLUDE_ASM(func_000A73D0);
INCLUDE_ASM(func_000A7440);

extern int D_0027EFD8;
extern short D_00284CEE;
extern short D_000E6CC0;

int func_000A7460(void)
{
    int flag;
    int one;

    flag = D_0027EFD8 == 0;
    one = 1;
    D_0027EFD8 = flag;
    D_00284CEE = one;
    D_000E6CC0 = one;
    return flag;
}

INCLUDE_ASM(func_000A7490);

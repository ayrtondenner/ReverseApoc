/*
 * src/ufo2p/u_00027a00.c: translation unit u_00027a00 of UFO2P.EXE, 0x00027A00..0x00028F80 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00027a00`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00027A00);
INCLUDE_ASM(func_00027AA0);
INCLUDE_ASM(func_00027B60);
INCLUDE_ASM(func_00027D30);
INCLUDE_ASM(func_00027DF0);
INCLUDE_ASM(func_00027FB0);
INCLUDE_ASM(func_00028100);

extern char D_000E6A15[];
int itoa(int, int, int);

int func_00028160(int r_eax)
{
    itoa(r_eax, (int)D_000E6A15, 10);
    return (int)D_000E6A15;
}

INCLUDE_ASM(func_00028180);
INCLUDE_ASM(func_000281A0);
INCLUDE_ASM(func_00028320);
INCLUDE_ASM(func_000286A0);
INCLUDE_ASM(func_00028AC0);
INCLUDE_ASM(func_00028E20);

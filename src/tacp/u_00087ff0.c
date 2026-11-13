/*
 * src/tacp/u_00087ff0.c: translation unit u_00087ff0 of TACP.EXE, 0x00087FF0..0x00089060 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00087ff0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00087FF0);
INCLUDE_ASM(func_00088040);
INCLUDE_ASM(func_00088210);
INCLUDE_ASM(func_00088390);
INCLUDE_ASM(func_00088410);
INCLUDE_ASM(func_00088450);
INCLUDE_ASM(func_000884A0);
INCLUDE_ASM(func_00088830);
INCLUDE_ASM(func_000888C0);
INCLUDE_ASM(func_00088F20);
INCLUDE_ASM(func_00089030);

/* func_00021180 returns a record pointer or NULL (callee listing not read). */
extern u8 *func_00021180(s32 a);

void func_000883F0(s32 a)
{
    u8 *p;

    p = func_00021180(a);
    if (p != 0) {
        p[4] = 0x28;
        p[5] = (u8)a;
    }
}

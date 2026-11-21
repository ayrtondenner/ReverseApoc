/*
 * src/ufo2p/u_000880f0.c: translation unit u_000880f0 of UFO2P.EXE, 0x000880F0..0x00089240 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000880f0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000880F0);
INCLUDE_ASM(func_00088150);
INCLUDE_ASM(func_000881C0);
INCLUDE_ASM(func_00088210);
INCLUDE_ASM(func_000886F0);
INCLUDE_ASM(func_00088720);
INCLUDE_ASM(func_00088CD0);

/* Declared without a prototype: the arguments take the default promotions. */
void func_00088210();

/* void: EAX only holds the callee's result at ret, the callers decide. */
void func_000886D0(u16 a, s16 b, s16 c)
{
    if ((s16)a != -1) {
        func_00088210(a, b, c, 1);
    }
}

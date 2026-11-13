/*
 * src/ufo2p/u_000940e0.c: translation unit u_000940e0 of UFO2P.EXE, 0x000940E0..0x00094280 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000940e0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00094120);

int func_000940E0(signed char v)
{
    if (v == 127) {
        return 0;
    }
    if (v > 74) {
        return 1;
    }
    if (v > 24) {
        return 2;
    }
    if (v > -25) {
        return 3;
    }
    if (v > -50) {
        return 4;
    }
    return 5;
}

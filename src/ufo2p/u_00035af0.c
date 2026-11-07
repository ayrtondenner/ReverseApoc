/*
 * src/ufo2p/u_00035af0.c: translation unit u_00035af0 of UFO2P.EXE, 0x00035AF0..0x00036240 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00035af0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00035AF0);
INCLUDE_ASM(func_00035C10);
INCLUDE_ASM(func_00035FF0);
INCLUDE_ASM(func_000361D0);

short func_00035F60(short a)
{
    short r;

    r = -1;
    if (a < 8) {
        r = a + 4;
        if (r >= 8) {
            r -= 8;
        }
    } else if (a == 8) {
        r = 14;
    } else if (a == 9) {
        r = 15;
    } else if (a == 10) {
        r = 12;
    } else if (a == 11) {
        r = 13;
    } else if (a == 12) {
        r = 10;
    } else if (a == 13) {
        r = 11;
    } else if (a == 14) {
        r = 8;
    } else if (a == 15) {
        r = 9;
    }
    return r;
}

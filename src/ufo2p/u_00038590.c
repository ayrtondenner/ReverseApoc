/*
 * src/ufo2p/u_00038590.c: translation unit u_00038590 of UFO2P.EXE, 0x00038590..0x00038AD0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00038590`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00038590);

short func_00038A50(short a, short b, short c, short d, int e, int f)
{
    short y = e;
    short z = f;

    if (c < z) {
        c = z - c;
    } else {
        c = c - z;
    }
    if (d > a) {
        a = d - a;
    } else {
        a = a - d;
    }
    if (y > b) {
        b = y - b;
    } else {
        b = b - y;
    }
    if (a >= b) {
        d = a;
        a = b;
    } else {
        d = b;
    }
    d = d * 4;
    a = a * 2;
    a = (d + a) / 2;
    c = c * 2;
    b = a;
    if (a < c) {
        a = c;
        c = b;
    }
    a = a * 4;
    c = c * 2;
    return (a + c) / 4;
}

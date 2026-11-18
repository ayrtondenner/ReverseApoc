/*
 * src/tacp/u_0001eb30.c: translation unit u_0001eb30 of TACP.EXE, 0x0001EB30..0x0001F270 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0001eb30`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0001EB30);
INCLUDE_ASM(func_0001EB80);
INCLUDE_ASM(func_0001EBD0);
INCLUDE_ASM(func_0001EC20);
INCLUDE_ASM(func_0001EC70);
INCLUDE_ASM(func_0001ECC0);
INCLUDE_ASM(func_0001ED10);
INCLUDE_ASM(func_0001EE60);
INCLUDE_ASM(func_0001EF90);
INCLUDE_ASM(func_0001F080);
INCLUDE_ASM(func_0001F100);
short func_0001F1F0(short a, short b, short c, short d, int e, int f)
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

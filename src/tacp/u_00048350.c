/*
 * src/tacp/u_00048350.c: translation unit u_00048350 of TACP.EXE, 0x00048350..0x00049E00 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00048350`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00048350);
INCLUDE_ASM(func_00049A10);
INCLUDE_ASM(func_00049B80);
INCLUDE_ASM(func_00049C30);

int func_00049B00(int a, int b, int c)
{
    int hi;
    int mid;
    int lo;

    if (a < 0) {
        a = -a;
    }
    if (b < 0) {
        b = -b;
    }
    if (c < 0) {
        c = -c;
    }
    if (a > b) {
        if (b > c) {
            hi = a;
            mid = b;
            lo = c;
        } else if (c > a) {
            hi = c;
            mid = a;
            lo = b;
        } else {
            hi = a;
            mid = c;
            lo = b;
        }
    } else {
        if (a > c) {
            hi = b;
            mid = a;
            lo = c;
        } else if (c > b) {
            hi = c;
            mid = b;
            lo = a;
        } else {
            hi = b;
            mid = c;
            lo = a;
        }
    }
    return lo * 4 + (mid - lo) * 3 + (hi - mid) * 2;
}

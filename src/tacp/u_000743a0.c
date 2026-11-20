/*
 * src/tacp/u_000743a0.c: translation unit u_000743a0 of TACP.EXE, 0x000743A0..0x00074420 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000743a0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

extern unsigned char D_000E6CCC;
extern short D_000E4D6E;
extern short D_002B6F68;
extern short D_002B6F6A;

int func_000743A0(short x, short y, short z)
{
    short flag;
    int res;

    flag = 0;
    res = 0;
    switch (D_000E6CCC) {
    case 0:
        flag = 1;
        break;
    case 1:
        if (z <= D_000E4D6E) {
            flag = 1;
        }
        break;
    case 2:
        if (z == D_000E4D6E) {
            flag = 1;
        }
        break;
    }
    if (flag && x >= D_002B6F6A && x < D_002B6F6A + 60
        && y >= D_002B6F68 && y < D_002B6F68 + 60) {
        res = 1;
    }
    return res;
}

/*
 * src/tacp/u_00015f80.c: translation unit u_00015f80 of TACP.EXE, 0x00015F80..0x00016EF0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00015f80`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

extern char D_000E4D76[];
extern char D_000E4D74[];
extern char D_000E4D7A[];
extern char D_000E4D78[];
int func_00016820(void);

int func_00015F80(void)
{
    int r_eax;

    *(short *)((D_000E4D76)) = 0;
    *(short *)((D_000E4D74)) = 0;
    *(short *)((D_000E4D7A)) = 352;
    *(short *)((D_000E4D78)) = 640;
    r_eax = func_00016820();
    return r_eax;
}

extern volatile short D_001B25B4;
extern short D_001B25A4, D_001B25A6;
extern int D_0027AD18;
extern char D_000E0DC0[], D_000E0DC4[], D_000E0DCC[], D_000E0DD4[];
signed char func_000A5CD0(char *);
int func_000A5BA0(int);

int func_00015FC0(void)
{
    int direction, a, b, c, d;
    direction = 0;
    a = 0;
    b = 0;
    c = 0;
    d = 0;
    if (D_001B25B4 || D_0027AD18) {
        if (D_001B25A6 < 1) {
            if (D_001B25A4 < 480) direction |= 8;
            if (D_001B25A4 >= 160) direction |= 1;
        } else if (D_001B25A6 >= 479) {
            if (D_001B25A4 < 480) direction |= 4;
            if (D_001B25A4 >= 160) direction |= 2;
        } else if (D_001B25A4 < 1) {
            if (D_001B25A6 < 264) direction |= 8;
            if (D_001B25A6 >= 88) direction |= 4;
        } else if (D_001B25A4 >= 639) {
            if (D_001B25A6 < 264) direction |= 1;
            if (D_001B25A6 >= 88) direction |= 2;
        }
    }
    if (!direction) {
        if (func_000A5BA0(func_000A5CD0(D_000E0DC0))) a = 1;
        if (func_000A5BA0(func_000A5CD0(D_000E0DC4))) b = 1;
        if (func_000A5BA0(func_000A5CD0(D_000E0DCC))) c = 1;
        if (func_000A5BA0(func_000A5CD0(D_000E0DD4))) d = 1;
        if (a && b) { a = 0; b = 0; }
        if (c && d) { c = 0; d = 0; }
        if (a) {
            if (d) direction = 1;
            if (c) direction = 8;
            if (!direction) direction = 9;
        }
        if (b) {
            if (d) direction = 2;
            if (c) direction = 4;
            if (!direction) direction = 6;
        }
        if (!a && !b) {
            if (d) direction = 3;
            if (c) direction = 12;
        }
    }
    return direction;
}
INCLUDE_ASM(func_000161B0);
INCLUDE_ASM(func_00016820);

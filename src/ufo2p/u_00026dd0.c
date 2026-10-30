/*
 * src/ufo2p/u_00026dd0.c: translation unit u_00026dd0 of UFO2P.EXE, 0x00026DD0..0x00027A00 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00026dd0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00026DD0);
INCLUDE_ASM(func_00026E20);
INCLUDE_ASM(func_00026FB0);
INCLUDE_ASM(func_00026FB2);
INCLUDE_ASM(func_00026FC0);
INCLUDE_ASM(func_00027020);

void *memset(void *dst, int c, unsigned n);

extern char D_000E69CD[];

void func_00026FD0(void)
{
    memset(D_000E69CD, 0, 30);
}

int func_00026FF0(char *s)
{
    int r;

    r = 0;
    if (s[0] == '-') {
        r = 1;
        if (s[1] == 'C' && s[2] == 'O' && s[3] == 'M') {
            r = 0;
        }
    }
    return r;
}

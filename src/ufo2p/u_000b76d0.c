/*
 * src/ufo2p/u_000b76d0.c: translation unit u_000b76d0 of UFO2P.EXE, 0x000B76D0..0x000B7740 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000b76d0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000B76D0);
INCLUDE_ASM(func_000B76F0);

extern unsigned char D_00138EFC[];

int key_take_first_pressed(void)
{
    int i;
    int r;
    int c;

    i = 1;
    r = 0;
    do {
        c = D_00138EFC[i];
        D_00138EFC[i] = 0;
        if (c != 0) {
            r = i;
            break;
        }
        i++;
    } while (i < 100);
    return r;
}

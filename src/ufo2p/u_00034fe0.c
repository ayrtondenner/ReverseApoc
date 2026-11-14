/*
 * src/ufo2p/u_00034fe0.c: translation unit u_00034fe0 of UFO2P.EXE, 0x00034FE0..0x000358B0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00034fe0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00035020);
INCLUDE_ASM(func_00035300);

extern char D_00160FD8[];

s32 func_00034FE0(void)
{
    char *p;
    s32 found;
    s32 count;
    s32 i;

    p = D_00160FD8;
    found = 0;
    count = 0;
    i = 0;
    do {
        if (*(s16 *)(p + 2) == -1) {
            count++;
            if (count >= 10) {
                found = 1;
                break;
            }
        }
        i++;
        p += 0x276;
    } while (i < 0x50);
    return found;
}

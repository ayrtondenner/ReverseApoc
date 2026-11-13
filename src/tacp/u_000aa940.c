/*
 * src/tacp/u_000aa940.c: translation unit u_000aa940 of TACP.EXE, 0x000AA940..0x000AB670 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000aa940`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000AA940);
INCLUDE_ASM(func_000AB060);
INCLUDE_ASM(func_000AB600);
INCLUDE_ASM(func_000AB650);

/* Returns a pointer to a byte array (a map tile) for (x, y, z). */
u8 *func_0001EB80(short x, short y, short z);

int func_000AB5B0(char *p)
{
    int x;
    int z;
    int y;
    u8 *c;

    x = *(short *)(p + 0xAA);
    z = *(short *)(p + 0xAE);
    y = *(short *)(p + 0xAC);
    if (z > 0) {
        do {
            c = func_0001EB80(x, y, z);
            if (c[0] != 0 || c[3] != 0) {
                break;
            }
            z--;
        } while (z > 0);
    }
    return z;
}

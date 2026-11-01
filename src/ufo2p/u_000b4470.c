/*
 * src/ufo2p/u_000b4470.c: translation unit u_000b4470 of UFO2P.EXE, 0x000B4470..0x000B4C20 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000b4470`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000B44C0);
INCLUDE_ASM(func_000B4590);
INCLUDE_ASM(func_000B48D0);
INCLUDE_ASM(func_000B4990);
INCLUDE_ASM(func_000B4A50);
INCLUDE_ASM(func_000B4B20);
INCLUDE_ASM(func_000B4B80);
INCLUDE_ASM(func_000B4BE0);

struct unk_009E {
    /* 0x00 */ u8 pad_00;
    /* 0x01 */ u8 a[0x34];
    /* 0x35 */ u8 b[0x34];
    /* 0x69 */ u8 c[0x34];
    /* 0x9D */ u8 pad_9D;
}; /* size: 0x9E */

extern struct unk_009E D_00173DC8[];

/* void: EAX is not set at ret */
void func_000B4470(int i)
{
    struct unk_009E *r;
    int j;

    r = &D_00173DC8[i];
    j = 0;
    while (j < 0x34) {
        j++;
        r->a[j] = 0;
        r->b[j] = 0;
        r->c[j] = 0;
    }
}

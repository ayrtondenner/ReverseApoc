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
INCLUDE_ASM(func_000B4BE0);

extern signed char D_000E0B88;
extern signed char D_000E0B89;
extern signed char D_000E0B8A;
extern signed char D_000E0B8B;
extern signed char D_000E0B8C;

int func_000B4B80(int x)
{
    int ret;

    ret = 1;
    switch (x) {
    case 0x2C:
        if (D_000E0B88 == 0) {
            ret = 0;
        }
        break;
    case 0x2D:
        if (D_000E0B89 == 0) {
            ret = 0;
        }
        break;
    case 0x2E:
        if (D_000E0B8A == 0) {
            ret = 0;
        }
        break;
    case 0x2F:
        if (D_000E0B8B == 0) {
            ret = 0;
        }
        break;
    case 0x30:
        if (D_000E0B8C == 0) {
            ret = 0;
        }
        break;
    }
    return ret;
}

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

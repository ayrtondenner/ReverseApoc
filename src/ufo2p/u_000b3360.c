/*
 * src/ufo2p/u_000b3360.c: translation unit u_000b3360 of UFO2P.EXE, 0x000B3360..0x000B33A0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000b3360`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

struct unk_00CE {
    /* 0x00 */ u8 pad_00[0x1A];
    /* 0x1A */ u16 id;
    /* 0x1C */ u8 pad_1C[0x61];
    /* 0x7D */ s8 state;
    /* 0x7E */ u8 pad_7E[0x50];
}; /* size: 0xCE */

extern struct unk_00CE D_00144918[];

int func_000B3360(int id)
{
    int i;
    int r;
    struct unk_00CE *p;

    r = -1;
    p = D_00144918;
    i = 0;
    do {
        if (p->state != -1 && p->id == id) {
            r = i;
            break;
        }
        i++;
        p++;
    } while (i < 180);
    return r;
}

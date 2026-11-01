/*
 * src/ufo2p/u_000ab080.c: translation unit u_000ab080 of UFO2P.EXE, 0x000AB080..0x000AB720 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000ab080`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000AB090);
INCLUDE_ASM(func_000AB240);
INCLUDE_ASM(func_000AB5F0);
INCLUDE_ASM(func_000AB6D0);

struct unk_000A {
    /* 0x00 */ u8 b0;
    /* 0x01 */ u8 pad_01[9];
}; /* size: 0x0A */

extern struct unk_000A D_000DE2B8[];

char flag_record_state(int a)
{
    char r;

    r = 0;
    if ((short)a == -1) {
        r = 0xff;
    }
    if (D_000DE2B8[(short)a].b0 != 0) {
        r = 1;
    }
    return r;
}

/*
 * src/ufo2p/u_000a74d0.c: translation unit u_000a74d0 of UFO2P.EXE, 0x000A74D0..0x000A7520 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000a74d0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

struct unk_001C {
    /* 0x00 */ s32 field_00;
    /* 0x04 */ u8 pad_04[0x18];
}; /* size: 0x1C */

struct unk_000A {
    /* 0x00 */ s32 field_00;
    /* 0x04 */ u8 pad_04[0x06];
}; /* size: 0x0A */

extern struct unk_001C D_000DD7F0[];
extern struct unk_000A D_000DE2B4[];

int func_000A74D0(int index)
{
    int base;

    base = D_000DD7F0[index].field_00;
    return (D_000DE2B4[index].field_00 * 200 + base) / (base * 2);
}

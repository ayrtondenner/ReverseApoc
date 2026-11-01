/*
 * src/tacp/u_000aa4e0.c: translation unit u_000aa4e0 of TACP.EXE, 0x000AA4E0..0x000AA940 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000aa4e0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000AA4E0);
INCLUDE_ASM(func_000AA4E4);
INCLUDE_ASM(func_000AA4F8);
INCLUDE_ASM(func_000AA500);

struct unk_0108 {
    /* 0x000 */ u8 pad_000[0xF4];
    /* 0x0F4 */ s16 unk_0F4;
    /* 0x0F6 */ u8 pad_0F6[0x2];
    /* 0x0F8 */ s16 unk_0F8;
    /* 0x0FA */ u8 pad_0FA[0xC];
    /* 0x106 */ u8 unk_106;
    /* 0x107 */ u8 unk_107;
}; /* size: 0x108 (at least) */

int func_000AA910(struct unk_0108 *p) {
    if (p->unk_0F8 == 0 || p->unk_0F4 != 0 || (p->unk_106 != 0 && p->unk_107 == 0)) {
        return 1;
    }
    return 0;
}

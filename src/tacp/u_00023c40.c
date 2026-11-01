/*
 * src/tacp/u_00023c40.c: translation unit u_00023c40 of TACP.EXE, 0x00023C40..0x00024F80 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00023c40`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00023D50);
INCLUDE_ASM(func_00023D80);
INCLUDE_ASM(func_00024030);
INCLUDE_ASM(func_000240C0);
INCLUDE_ASM(func_00024280);
INCLUDE_ASM(func_00024390);
INCLUDE_ASM(func_00024640);
INCLUDE_ASM(func_000246F0);
INCLUDE_ASM(func_000247B0);
INCLUDE_ASM(func_00024A20);
INCLUDE_ASM(func_00024B20);
INCLUDE_ASM(func_00024B30);
INCLUDE_ASM(func_00024B7D);
INCLUDE_ASM(func_00024B86);
INCLUDE_ASM(func_00024B90);
INCLUDE_ASM(func_00024B95);

struct unk_049C {
    /* 0x000 */ u8 pad_000[0xF4];
    /* 0x0F4 */ s16 unk_0F4;
    /* 0x0F6 */ s16 pad_0F6;
    /* 0x0F8 */ s16 unk_0F8;
    /* 0x0FA */ u8 pad_0FA[0x0C];
    /* 0x106 */ u8 unk_106;
    /* 0x107 */ u8 pad_107[0x1B6];
    /* 0x2BD */ u8 unk_2BD;
    /* 0x2BE */ u8 pad_2BE;
    /* 0x2BF */ u8 unk_2BF;
    /* 0x2C0 */ u8 pad_2C0[0x1DC];
}; /* size: 0x49C */

extern struct unk_049C D_00109ED0[];

int func_00023C40(short idx) {
    struct unk_049C *p;
    s16 v;
    int result;

    p = &D_00109ED0[idx];
    v = p->unk_0F8;
    result = 0;
    if (v != 0 &&p->unk_0F4 == 0 && p->unk_106 == 0) {
        result = 1;
    }
    if (p->unk_2BF != 0) {
        result = 1;
    }
    if (p->unk_2BD == 2) {
        result = 1;
    }
    return result;
}

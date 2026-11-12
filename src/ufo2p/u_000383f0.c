/*
 * src/ufo2p/u_000383f0.c: translation unit u_000383f0 of UFO2P.EXE, 0x000383F0..0x00038550 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000383f0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000383F0);
INCLUDE_ASM(func_00038490);

struct unk_00F8 {
    /* 0x00 */ u8 pad_00[0x30];
    /* 0x30 */ s16 f_30;
    /* 0x32 */ s16 f_32;
    /* 0x34 */ s16 f_34;
    /* 0x36 */ u8 pad_36[0x30];
    /* 0x66 */ s16 f_66;
    /* 0x68 */ u8 pad_68[0x8E];
    /* 0xF6 */ s16 f_F6;
}; /* size: 0xF8 */

/* Callee: four arguments in eax, edx, ebx, ecx; result unused by the caller. */
extern void func_00038590(int a, int b, int c, int d);

void func_00038510(struct unk_00F8 *p)
{
    s16 sVar1;

    if (p->f_66 < 8 && p->f_F6 == 3) {
        sVar1 = p->f_66 + 0x72;
    } else {
        sVar1 = 0x71;
    }
    func_00038590(sVar1, p->f_30, p->f_32, p->f_34);
}

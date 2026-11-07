/*
 * src/tacp/u_000b1de0.c: translation unit u_000b1de0 of TACP.EXE, 0x000B1DE0..0x000B2040 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000b1de0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000B1E50);
INCLUDE_ASM(func_000B1FE0);

struct unk_049C {
    /* 0x000 */ s16 kind;
    /* 0x002 */ u8 pad_002[0x1E];
    /* 0x020 */ s16 unk_020;
    /* 0x022 */ u8 pad_022[0x04];
    /* 0x026 */ s16 unk_026;
    /* 0x028 */ u8 pad_028[0x07];
    /* 0x02F */ u8 unk_02F;
    /* 0x030 */ u8 pad_030[0x34];
    /* 0x064 */ s16 unk_064;
    /* 0x066 */ u8 pad_066[0x436];
}; /* size: 0x49C */

extern struct unk_049C tacrec_table[];

s16 func_000B1DE0(s16 a, s16 b)
{
    struct unk_049C *p;
    s16 i;
    s16 best;

    p = tacrec_table;
    best = 0;
    for (i = 0; i < 60; i++, p++) {
        if (p->kind != -1 && p->unk_064 != 0 && p->unk_020 == b && p->unk_026 == a
            && (s16)p->unk_02F > best) {
            best = p->unk_02F;
        }
    }
    return best;
}

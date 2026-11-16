/*
 * src/tacp/u_0009c350.c: translation unit u_0009c350 of TACP.EXE, 0x0009C350..0x0009D110 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0009c350`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0009C350);
INCLUDE_ASM(func_0009C600);
INCLUDE_ASM(func_0009C820);
INCLUDE_ASM(func_0009CA00);
INCLUDE_ASM(func_0009CAC0);
INCLUDE_ASM(func_0009CFF0);

struct unk_049C {
    /* 0x000 */ s16 unk_00;
    /* 0x002 */ u8 pad_02[0x1e];
    /* 0x020 */ s16 unk_20;
    /* 0x022 */ u8 pad_22[2];
    /* 0x024 */ s16 unk_24;
    /* 0x026 */ s16 unk_26;
    /* 0x028 */ u8 pad_28[0x3c];
    /* 0x064 */ s16 unk_64;
    /* 0x066 */ u8 pad_66[0x16];
    /* 0x07c */ u8 unk_7C;
    /* 0x07d */ u8 pad_7d[3];
    /* 0x080 */ s16 unk_80;
    /* 0x082 */ u8 pad_82[0x23a];
    /* 0x2bc */ u8 unk_2BC;
    /* 0x2bd */ u8 pad_2bd[0x1df];
}; /* size: 0x49C */

extern struct unk_049C tacrec_table[];
extern char D_0011B360[];
extern s16 D_000E6D64;
extern u8 D_000E6D66;

s32 func_0009C960(s32 param_1, s32 param_2)
{
    struct unk_049C *rec;
    struct unk_049C *p;
    s32 match;
    s32 value;
    s32 first;

    rec = tacrec_table;
    if (rec < (struct unk_049C *)D_0011B360) {
        do {
            p = rec;
            first = rec->unk_20;
            value = param_2;
            match = first == param_1 && (p->unk_24 == D_000E6D64 || D_000E6D66 != 0)
                && p->unk_26 == value && p->unk_00 != -1 && p->unk_64 > 0
                && p->unk_80 < p->unk_64 && p->unk_7C == 0;
            if (match && (rec->unk_2BC & 2) == 0) {
                return 0;
            }
            rec++;
        } while (rec < (struct unk_049C *)D_0011B360);
    }
    return 1;
}

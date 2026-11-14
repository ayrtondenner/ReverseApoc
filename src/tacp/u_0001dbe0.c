/*
 * src/tacp/u_0001dbe0.c: translation unit u_0001dbe0 of TACP.EXE, 0x0001DBE0..0x0001DF90 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0001dbe0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0001DBE0);
INCLUDE_ASM(func_0001DCD0);
INCLUDE_ASM(func_0001DED0);
struct unk_049C {
    /* 0x00 */ s16 kind;
    /* 0x02 */ u8 pad_02[0x62];
    /* 0x64 */ s16 unk_064;
    /* 0x66 */ u8 pad_66[0x1A];
    /* 0x80 */ s16 unk_080;
    /* 0x82 */ u8 pad_82[0x42];
    /* 0xC4 */ s16 unk_0C4;
    /* 0xC6 */ u8 pad_C6[0x1A];
    /* 0xE0 */ s16 unk_0E0;
    /* 0xE2 */ s16 unk_0E2;
    /* 0xE4 */ s16 unk_0E4;
    /* 0xE6 */ s16 unk_0E6;
    /* 0xE8 */ s16 unk_0E8;
    /* 0xEA */ u8 pad_EA[0x3B2];
}; /* size: 0x49C */

extern struct unk_049C tacrec_table[];
extern struct unk_049C D_0011AEC4;
extern int func_00022060(struct unk_049C *p);

struct unk_049C *func_0001DEF0(int a1, int a2, int a3)
{
    struct unk_049C *p;
    int v;

    p = &D_0011AEC4;
    if (p >= tacrec_table) {
        do {
            if (p->kind != -1 && p->unk_064 != 0 && p->unk_064 > p->unk_080) {
                v = func_00022060(p);
                if (a3 >= p->unk_0E4 && a3 < v + p->unk_0C4 &&
                    a1 >= p->unk_0E0 && a1 < p->unk_0E6 &&
                    a2 >= p->unk_0E2 && a2 < p->unk_0E8) {
                    return p;
                }
            }
            p--;
        } while (p >= tacrec_table);
    }
    return 0;
}

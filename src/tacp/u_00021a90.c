/*
 * src/tacp/u_00021a90.c: translation unit u_00021a90 of TACP.EXE, 0x00021A90..0x00023C00 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00021a90`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00021A90);
INCLUDE_ASM(func_00021B30);
INCLUDE_ASM(func_00021B70);
INCLUDE_ASM(func_00021BB0);
INCLUDE_ASM(func_00021E30);
INCLUDE_ASM(func_00021F50);
INCLUDE_ASM(func_00021FD0);
INCLUDE_ASM(func_00022060);
INCLUDE_ASM(func_00022110);
INCLUDE_ASM(func_00022140);
INCLUDE_ASM(func_00022210);
INCLUDE_ASM(func_000222A0);
INCLUDE_ASM(func_000225E0);
INCLUDE_ASM(func_00022670);
INCLUDE_ASM(func_00022A30);
INCLUDE_ASM(func_00023010);
INCLUDE_ASM(func_00023130);
INCLUDE_ASM(func_00023150);
INCLUDE_ASM(func_00023190);
INCLUDE_ASM(func_00023720);
INCLUDE_ASM(func_00023890);
INCLUDE_ASM(func_00023940);
INCLUDE_ASM(func_00023A40);
INCLUDE_ASM(func_00023AA0);
INCLUDE_ASM(func_00023BB0);

struct unk_049C {
    /* 0x000 */ s16 id;
    /* 0x002 */ u8 pad_002[0x49A];
}; /* size: 0x49C */

/* Only the fields tacrec_count_live_slots reads; the full size is not known. */
struct unk_0286 {
    /* 0x000 */ u8 pad_000[0x64];
    /* 0x064 */ s16 x64;
    /* 0x066 */ u8 pad_066[0x1A];
    /* 0x080 */ s16 x80;
    /* 0x082 */ u8 pad_082[0x1F8];
    /* 0x27A */ u8 idx[6];
    /* 0x280 */ u8 active[6];
}; /* size: 0x286 (at least) */

extern struct unk_049C tacrec_table[];

int tacrec_count_live_slots(struct unk_0286 *s)
{
    int count;
    int i;

    count = 0;
    if (s->x64 > s->x80) {
        for (i = 0; i < 6; i++) {
            if (s->active[i] != 0 && tacrec_table[s->idx[i]].id != -1) {
                count++;
            }
        }
    }
    return count;
}

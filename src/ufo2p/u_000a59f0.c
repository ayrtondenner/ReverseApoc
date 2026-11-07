/*
 * src/ufo2p/u_000a59f0.c: translation unit u_000a59f0 of UFO2P.EXE, 0x000A59F0..0x000A5BA0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000a59f0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000A5A50);

struct unk_00CE {
    /* 0x00 */ u8 pad_00[0x7D];
    /* 0x7D */ s8 field_7D;
    /* 0x7E */ u8 pad_7E[0x2A];
    /* 0xA8 */ u32 field_A8;
    /* 0xAC */ s32 field_AC;
    /* 0xB0 */ u8 pad_B0[0x1E];
}; /* size: 0xCE */

struct unk_0006 {
    /* 0x00 */ u32 field_00;
    /* 0x04 */ u16 field_04;
}; /* size: 0x06 */

extern struct unk_00CE slot_table_records[];
extern struct unk_0006 D_00142EEA[];

void func_000A59F0(char arg)
{
    struct unk_00CE *p;
    unsigned int i;

    if (arg == 0) {
        for (p = slot_table_records, i = 0; i < 0xB4; i++, p++) {
            if (p->field_7D != -1 && p->field_A8 > 0) {
                p->field_A8 = D_00142EEA[p->field_AC].field_00;
            }
        }
    }
}

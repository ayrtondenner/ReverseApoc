/*
 * src/ufo2p/u_000a59f0.c: translation unit u_000a59f0 of UFO2P.EXE, 0x000A59F0..0x000A5BA0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000a59f0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

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

/* Records addressed by func_000A5A50; their fields are not read here, only their sizes. */
struct unk_00E2 {
    /* 0x00 */ u8 data[0xE2];
}; /* size: 0xE2 */

struct unk_0276 {
    /* 0x000 */ u8 data[0x276];
}; /* size: 0x276 */

struct unk_02BE {
    /* 0x000 */ u8 data[0x2BE];
}; /* size: 0x2BE */

extern s16 D_000D4D7C;
extern struct unk_00E2 *D_000D4D78;
extern struct unk_00E2 *D_0018276C;
extern s16 D_00183A56, D_00183A60, D_00183A54;
extern s16 D_00183A58[];
extern s16 D_00183952[], D_001839D4[];
extern s16 D_0018391E[][13], D_00183938[];
extern struct unk_0276 D_00160FD8[];
extern struct unk_02BE D_000D942E[];
extern struct unk_0276 *D_00182AD4[], *D_00182BD8[];
extern struct unk_02BE *D_00182AA0[];
extern struct unk_00CE *D_00182A6C[][13];
extern s16 D_000D4E28, hover_info_changed;
extern s32 D_000D5058, D_00182A58;

/* The bytes show no result (EAX is only a loop counter at ret), so void. */
void func_000A5A50(void)
{
    s16 i, j;
    int k;

    if (D_000D4D7C != 0)
        D_000D4D78 = (struct unk_00E2 *)((s32)D_0018276C + D_000D4D7C * 226);
    for (i = 0; i < D_00183A56; i++)
        D_00182AD4[i] = &D_00160FD8[D_00183952[i]];
    for (j = 0; j < 4; j++) {
        for (i = 0; i < D_00183A58[j]; i++) {
            k = i;
            D_00182A6C[j + 3][k] = &slot_table_records[D_0018391E[j + 3][k]];
        }
    }
    for (i = 0; i < D_00183A60; i++)
        D_00182BD8[i] = &D_00160FD8[D_001839D4[i]];
    for (i = 0; i < D_00183A54; i++)
        D_00182AA0[i] = &D_000D942E[D_00183938[i]];
    D_000D4E28 = 0;
    D_000D5058 = 1;
    D_00182A58 = 0;
    hover_info_changed = 1;
}

/*
 * src/ufo2p/u_00051be0.c: translation unit u_00051be0 of UFO2P.EXE, 0x00051BE0..0x00051D00 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00051be0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00051BE0);

struct unk_00C9 {
    /* 0x00 */ u8 pad_00[0xB3];
    /* 0xB3 */ u8 unk_B3;
    /* 0xB4 */ u8 pad_B4[0x14];
    /* 0xC8 */ u8 unk_C8;
}; /* size: 0xC9 */

extern struct unk_00C9 *D_00182B08[];
extern short D_00183A42;
extern short D_00183A58;
extern short hover_info_changed;
extern short D_00183A80;

void func_0006BD50(void);

void func_00051C70(void)
{
    int value;
    int i;
    u8 mode;
    struct unk_00C9 *rec;

    if (D_00183A58 > 0) {
        mode = D_00182B08[D_00183A42]->unk_C8;
        if ((value = mode) == 2)
            value = 0;
        else
            value = 2;
        for (i = 0; i < D_00183A58; i++) {
            rec = D_00182B08[i];
            if (rec->unk_B3 != 2)
                rec->unk_C8 = value;
        }
        hover_info_changed = 1;
        D_00183A80 = 1;
        func_0006BD50();
    }
}

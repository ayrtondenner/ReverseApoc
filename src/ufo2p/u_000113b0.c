/*
 * src/ufo2p/u_000113b0.c: translation unit u_000113b0 of UFO2P.EXE, 0x000113B0..0x00011430 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000113b0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000113B0);

struct unk_00CE {
    /* 0x00 */ u8 pad_00[0x7C];
    /* 0x7C */ u8 unk_7C;
    /* 0x7D */ u8 unk_7D;
    /* 0x7E */ u8 pad_7E[0x50];
}; /* size: 0xCE */

extern u8 D_000D5060;
extern struct unk_00CE slot_table_records[];

int func_000113F0(void)
{
    u8 saved;
    u8 owner;
    struct unk_00CE *rec;
    int result;
    s16 index;
    int found;

    saved = D_000D5060;
    rec = slot_table_records;
    result = 0;
    index = 0;
    do {
        if (rec->unk_7D == 1) {
            owner = rec->unk_7C;
            if (owner == saved) {
                result = 1;
                break;
            }
        }
        index++;
        rec++;
    } while (index < 0xB4);
    found = result;
    result = saved;
    D_000D5060 = result;
    return found;
}

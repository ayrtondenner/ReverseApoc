/*
 * src/ufo2p/u_00073000.c: translation unit u_00073000 of UFO2P.EXE, 0x00073000..0x000738C0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00073000`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00073060);
INCLUDE_ASM(func_00073170);
INCLUDE_ASM(func_000731D0);
INCLUDE_ASM(func_00073210);
INCLUDE_ASM(func_000734F0);

struct unk_0276 {
    /* 0x000 */ u8 data[0x276];
}; /* size: 0x276 */

struct unk_00CE {
    /* 0x00 */ u8 pad_00[0x7D];
    /* 0x7D */ u8 kind;
    /* 0x7E */ s16 owner;
    /* 0x80 */ u8 pad_80[0x4E];
}; /* size: 0xCE */

extern struct unk_0276 D_00160FD8[];
extern struct unk_00CE slot_table_records[];

s16 func_00073000(struct unk_0276 *unit, int index)
{
    struct unk_00CE *rec;
    int count;
    s16 i;

    rec = slot_table_records;
    count = 0;
    if (unit != 0) {
        index = unit - D_00160FD8;
    }
    for (i = 0; i < 0xB4; i++, rec++) {
        if (rec->kind == 3 && rec->owner == (s16)index) {
            count++;
        }
    }
    return count;
}

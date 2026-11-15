/*
 * src/ufo2p/u_00073000.c: translation unit u_00073000 of UFO2P.EXE, 0x00073000..0x000738C0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00073000`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00073170);
INCLUDE_ASM(func_000731D0);
INCLUDE_ASM(func_00073210);
INCLUDE_ASM(func_000734F0);

struct unk_0276 {
    /* 0x000 */ u8 data[0x276];
}; /* size: 0x276 */

struct unk_0008 {
    /* 0x00 */ s16 owner;
    /* 0x02 */ s16 index;
    /* 0x04 */ s16 amount;
    /* 0x06 */ u8 kind;
    /* 0x07 */ u8 pad_07;
}; /* size: 0x8 */

struct unk_0012 {
    /* 0x00 */ u8 pad_00[2];
    /* 0x02 */ u8 kind;
    /* 0x03 */ u8 index;
    /* 0x04 */ u8 pad_04[8];
    /* 0x0C */ u8 value;
    /* 0x0D */ u8 pad_0D[5];
}; /* size: 0x12 */

struct unk_0012v {
    /* 0x00 */ u8 value;
    /* 0x01 */ u8 pad_01[0x11];
}; /* size: 0x12 */

struct unk_000C {
    /* 0x00 */ u8 pad_00;
    /* 0x01 */ s8 divisor;
    /* 0x02 */ u8 pad_02[6];
    /* 0x08 */ s16 flag;
    /* 0x0A */ u8 pad_0A[2];
}; /* size: 0xC */

struct unk_0018 {
    /* 0x00 */ u8 value;
    /* 0x01 */ u8 pad_01[0x17];
}; /* size: 0x18 */

extern struct unk_0276 D_00160FD8[];
extern struct unk_0008 D_00144118[];
extern struct unk_0012 D_0013A006[];
extern struct unk_0012v D_0013A012[];
extern struct unk_000C D_0013A624[];
extern struct unk_0018 D_001296BA[];
extern s16 D_000DD53C[];

s16 func_00073060(struct unk_0276 *unit, s16 index)
{
    struct unk_0008 *rec;
    s16 count;
    s16 i;
    s8 divisor;
    struct unk_0012 *item;
    struct unk_000C *ent;
    int flag;
    int num;
    u8 kind;

    rec = D_00144118;
    count = 0;
    if (unit != 0) index = unit - D_00160FD8;
    for (i = 0; i < 0x100; i++, rec++) {
        if (rec->owner == index) {
            kind = rec->kind;
            switch (kind) {
            case 1:
                item = &D_0013A006[rec->index];
                divisor = 1;
                if (item->kind == 2) {
                    ent = &D_0013A624[item->index];
                    flag = ent->flag;
                    if (flag != -1)
                        divisor = ent->divisor;
                }
                count += D_0013A012[rec->index].value * (int)rec->amount / divisor;
                break;
            case 2:
                count += D_001296BA[rec->index].value * rec->amount;
                break;
            case 3:
                count += D_000DD53C[rec->index] * rec->amount;
                break;
            default:
                break;
            }
        }
    }
    return count;
}

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

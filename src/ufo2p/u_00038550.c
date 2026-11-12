/*
 * src/ufo2p/u_00038550.c: translation unit u_00038550 of UFO2P.EXE, 0x00038550..0x00038590 (D-11).
 */
#include "common.h"

struct unk_001E {
    /* 0x00 */ u8 pad_00[0x10];
    /* 0x10 */ u16 f_10;
    /* 0x12 */ u8 pad_12[4];
    /* 0x16 */ s16 f_16;
    /* 0x18 */ s16 f_18;
    /* 0x1A */ s16 f_1A;
    /* 0x1C */ s16 f_1C;
}; /* size: 0x1E */

extern void func_00038590(short a, short b, short c, short d);

void func_00038550(struct unk_001E *p)
{
    short id;

    short t;

    t = p->f_1C;
    if (t < 8) {
        id = t + 0x61;
    } else {
        id = 0x68;
    }
    if (p->f_10 > 0x40) {
        id += 8;
    }
    func_00038590(id, p->f_16, p->f_18, p->f_1A);
}

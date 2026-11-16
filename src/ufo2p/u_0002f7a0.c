/*
 * src/ufo2p/u_0002f7a0.c: translation unit u_0002f7a0 of UFO2P.EXE, 0x0002F7A0..0x0002FA60 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0002f7a0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0002F7F0);
INCLUDE_ASM(func_0002F9D0);

/* 0x2E-byte record; only the fields the function reads are named. */
struct unk_002E {
    /* 0x00 */ u8 pad_00[4];
    /* 0x04 */ s32 value;
    /* 0x08 */ u8 pad_08[4];
    /* 0x0C */ s32 flag;
    /* 0x10 */ u8 pad_10[8];
    /* 0x18 */ u32 limit;
    /* 0x1C */ u8 active;
    /* 0x1D */ u8 pad_1d[0x11];
}; /* size: 0x2E */

extern struct unk_002E D_00170CD0[];
extern struct unk_002E D_00170E9C[];
extern s32 D_001A1138;

u32 func_00011430(void);
void func_0002FA60(struct unk_002E *p);

void func_0002F7A0(void)
{
    u32 c;
    u32 t;
    struct unk_002E *p;

    c = func_00011430();
    p = D_00170CD0;
    t = c;
    if (p >= D_00170E9C) {
        return;
    }
    do {
        if (p->flag != 0 && p->value == D_001A1138) {
            t -= p->limit;
            if (t > 4 || p->active != 0) {
                return;
            }
            func_0002FA60(p);
            return;
        }
        p++;
    } while (p < D_00170E9C);
}

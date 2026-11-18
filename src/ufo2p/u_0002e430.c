/*
 * src/ufo2p/u_0002e430.c: translation unit u_0002e430 of UFO2P.EXE, 0x0002E430..0x0002E540 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0002e430`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

struct unk_0034 {
    /* 0x00 */ u8 pad_00[0x20];
    /* 0x20 */ s32 field_20;
    /* 0x24 */ u8 pad_24[0x10];
};
extern struct unk_0034 D_00141CA8[];
extern struct unk_0034 D_00142668[];
extern int D_001A1128;
extern int D_001A1138;
extern int D_001A1144;

void func_0002E430(int a)
{
    struct unk_0034 *p;
    int zero;

    zero ^= zero;
    p = D_00141CA8;
    D_001A1128 = zero;
    D_001A1144 = zero;
    D_001A1138 = zero;
    if (p < D_00142668) {
        do {
            p++;
            p[-1].field_20 = 0;
        } while (p < D_00142668);
    }
}
INCLUDE_ASM(func_0002E470);
INCLUDE_ASM(func_0002E480);

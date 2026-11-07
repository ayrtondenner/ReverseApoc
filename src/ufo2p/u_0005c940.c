/*
 * src/ufo2p/u_0005c940.c: translation unit u_0005c940 of UFO2P.EXE, 0x0005C940..0x0005DB20 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0005c940`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0005C980);
INCLUDE_ASM(func_0005CAD0);
INCLUDE_ASM(func_0005CC00);
INCLUDE_ASM(func_0005CCF0);
INCLUDE_ASM(func_0005CD00);
INCLUDE_ASM(func_0005CD90);
INCLUDE_ASM(func_0005CDC0);
INCLUDE_ASM(func_0005CE00);
INCLUDE_ASM(func_0005CE50);
INCLUDE_ASM(func_0005CEB0);
INCLUDE_ASM(func_0005D070);
INCLUDE_ASM(func_0005D1B0);
INCLUDE_ASM(func_0005D210);
INCLUDE_ASM(func_0005DAA0);

struct unk_0034 {
    /* 0x00 */ u8 data[0x34];
}; /* size: 0x34 */

extern struct unk_0034 D_00153068[];
extern s32 *D_001715F0;
extern s32 *D_001715F4;
extern u8 *D_00182DFC;

struct unk_0034 *func_0005C940(s32 x, s32 y, s32 z)
{
    u8 *p;

    p = (u8 *)D_001715F0;
    z = ((s32 *)p)[z];
    p = D_00182DFC;
    z += z;
    p += z;
    z = (s32)D_001715F4;
    y = ((s32 *)z)[y];
    y += y;
    x += x;
    y += (s32)p;
    y += x;
    return &D_00153068[*(u16 *)y];
}

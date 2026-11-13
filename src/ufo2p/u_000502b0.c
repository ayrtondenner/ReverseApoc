/*
 * src/ufo2p/u_000502b0.c: translation unit u_000502b0 of UFO2P.EXE, 0x000502B0..0x00050C60 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000502b0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000502B0);
INCLUDE_ASM(func_000504E0);
INCLUDE_ASM(func_000505A0);
INCLUDE_ASM(func_00050920);
INCLUDE_ASM(func_000509C0);
INCLUDE_ASM(func_00050A20);
INCLUDE_ASM(func_00050A80);
INCLUDE_ASM(func_00050AE0);
INCLUDE_ASM(func_00050BB0);

extern short D_000D504C;
extern short hover_info_changed;
extern short D_00183A80;
extern int D_000D4D58;
extern int D_000D4D5C;
extern unsigned short D_000D5064;
extern int D_000E12F8;

void func_0005EDF0();

void func_00050970(void)
{
    register int one;
    int two;
    short zero;
    short wide;

    if (D_000D4D58 == 600) {
        one = 1;
        func_0005EDF0();
        D_000E12F8 = one;
    }
    two = 1;
    zero = 0;
    wide = 1;
    D_000D4D58 = two;
    D_000D4D5C = two;
    D_000D5064 = zero;
    hover_info_changed = wide;
    D_00183A80 = wide;
}

short func_00050C30(void)
{
    short flag;
    short one;
    short wide;
    unsigned char zero;

    flag = D_000D504C;
    one = 1;
    zero = flag == 0;
    hover_info_changed = one;
    wide = zero;
    D_00183A80 = one;
    D_000D504C = wide + (flag - flag);
    return wide;
}

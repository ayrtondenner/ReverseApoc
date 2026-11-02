/*
 * src/ufo2p/u_00051d00.c: translation unit u_00051d00 of UFO2P.EXE, 0x00051D00..0x00051E60 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00051d00`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00051D00);
INCLUDE_ASM(func_00051D40);
INCLUDE_ASM(func_00051D80);

void func_00051DA0(void)
{
    return;
}

INCLUDE_ASM(func_00051DD0);

extern int D_000D5058;
extern short hover_info_changed;
extern short D_00183A80;

/* flags_set_d5058_and_pair: set three engine flags to one
 * Stores 1 into the 32-bit flag at 0x000D5058 and into the two 16-bit flags at
 * 0x00183A78 and 0x00183A80. The same 16-bit pair is also set by 0x00052060 and
 * 0x00052080, each next to a different 32-bit flag (0x000E12F0). What the flags
 * mean is not read yet: the name says what the code does, not why.
 * Address: UFO2P.EXE 0x00051DB0
 * Evidence: call: no direct caller; reached through a pointer only (fixup row, mechanics member)
 * Evidence: call: writes 1 to 0x000D5058 (dword) and to 0x00183A78 and 0x00183A80 (words)
 */
void flags_set_d5058_and_pair(void)
{
    D_000D5058 = 1;
    hover_info_changed = 1;
    D_00183A80 = 1;
}

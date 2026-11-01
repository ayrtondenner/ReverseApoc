/*
 * src/ufo2p/u_00052080.c: translation unit u_00052080 of UFO2P.EXE, 0x00052080..0x00053660 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00052080`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000520A0);
INCLUDE_ASM(func_000520C0);
INCLUDE_ASM(func_000520E0);
INCLUDE_ASM(func_00052100);
INCLUDE_ASM(func_00052150);

extern int D_000E12F0;
extern short D_00183A80;
extern short hover_info_changed;

/* button_group_select_1: select button one of a six-button group
 * Button callback: stores index 1 as the group's selection and sets the two
 * short flags D_00183A80 and hover_info_changed to 1, as every sibling setter does.
 * The siblings 0x00052060, 0x000520A0, 0x000520C0, 0x000520E0 and 0x00052100
 * store 0, 2, 3, 4 and 5 instead.
 * Address: UFO2P.EXE 0x00052080
 * Evidence: call: 0x00052150 pushes 0x00052080 as the callback of its second button (0x0005338E)
 * Evidence: call: 0x00052150 draws that button pressed while D_000E12F0 == 1 (0x00053352)
 */
void button_group_select_1(void)
{
    D_000E12F0 = 1;
    D_00183A80 = 1;
    hover_info_changed = 1;
}

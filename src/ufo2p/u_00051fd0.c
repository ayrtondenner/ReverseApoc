/*
 * src/ufo2p/u_00051fd0.c: translation unit u_00051fd0 of UFO2P.EXE, 0x00051FD0..0x00052080 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00051fd0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00051FD0);

extern int D_000E12F0;
extern short D_00183A80;
extern short D_00183A78;

/* button_group_select_0: select button zero of a six-button group
 * Button callback: stores index 0 as the group's selection (D_000E12F0) and sets
 * the two short flags D_00183A80 and D_00183A78 to 1, as every sibling setter does.
 * The siblings 0x00052080, 0x000520A0, 0x000520C0, 0x000520E0 and 0x00052100
 * store 1, 2, 3, 4 and 5 instead.
 * Address: UFO2P.EXE 0x00052060
 * Evidence: call: no direct caller; the sibling 0x00052080 is a button callback pushed by 0x00052150
 * Evidence: call: 0x00052150 draws a group button pressed by comparing D_000E12F0 with its index
 */
void button_group_select_0(void)
{
    D_000E12F0 = 0;
    D_00183A80 = 1;
    D_00183A78 = 1;
}

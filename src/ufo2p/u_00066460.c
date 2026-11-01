/*
 * src/ufo2p/u_00066460.c: translation unit u_00066460 of UFO2P.EXE, 0x00066460..0x00066C50 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00066460`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00066460);
INCLUDE_ASM(func_00066580);
INCLUDE_ASM(func_00066780);

extern int D_001A3EFC;

void dialog_button_press_cb(void)
{
    D_001A3EFC = 1;
}

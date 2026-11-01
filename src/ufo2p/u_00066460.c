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

/* dialog_button_press_cb: button callback that raises a flag
 * Sets the 32-bit flag D_001A3EFC to 1. The flag's readers are not traced yet.
 * Address: UFO2P.EXE 0x00066760
 * Evidence: call: 0x00066580 passes it twice (0x00066685, 0x000666CD) as a button callback to 0x0002E640
 * Evidence: call: same shape as 0x00066C50, which 0x00066780 hands to 0x0002E640 and whose flag ends its loop
 */
void dialog_button_press_cb(void)
{
    D_001A3EFC = 1;
}

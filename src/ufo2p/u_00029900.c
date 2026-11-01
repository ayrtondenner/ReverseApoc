/*
 * src/ufo2p/u_00029900.c: translation unit u_00029900 of UFO2P.EXE, 0x00029900..0x0002B810 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00029900`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00029900);
INCLUDE_ASM(func_00029910);
INCLUDE_ASM(func_0002A250);
INCLUDE_ASM(func_0002AD90);
INCLUDE_ASM(func_0002AF40);
INCLUDE_ASM(func_0002B320);

extern int D_001A112C;

/* void: EAX is not set before ret */
void ui_request_screen_exit(void)
{
    D_001A112C = 1;
}

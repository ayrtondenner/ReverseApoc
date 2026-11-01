/*
 * src/ufo2p/u_000105d0.c: translation unit u_000105d0 of UFO2P.EXE, 0x000105D0..0x000113B0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000105d0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000105D0);
INCLUDE_ASM(func_00010940);

extern int D_000E1328;

/* void: EAX is not set before the ret. */
void confirm_flag_set(void)
{
    D_000E1328 = 1;
}

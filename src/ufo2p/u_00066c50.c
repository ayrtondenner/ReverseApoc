/*
 * src/ufo2p/u_00066c50.c: translation unit u_00066c50 of UFO2P.EXE, 0x00066C50..0x00067DE0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00066c50`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00066C70);
INCLUDE_ASM(func_000670B0);
INCLUDE_ASM(func_00067550);
INCLUDE_ASM(func_00067870);
INCLUDE_ASM(func_00067930);

extern int confirm_is_accepted;

void confirm_on_accept(void)
{
    confirm_is_accepted = 1;
}

extern int confirm_is_cancelled;

void confirm_on_cancel(void)
{
    confirm_is_cancelled = 1;
}

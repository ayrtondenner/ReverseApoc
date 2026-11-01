/*
 * src/ufo2p/u_000b5fb0.c: translation unit u_000b5fb0 of UFO2P.EXE, 0x000B5FB0..0x000B63C0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000b5fb0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000B5FB0);
INCLUDE_ASM(func_000B5FD0);

extern int is_level_update_enabled;

/* level_update_disable: disable the level update routine
 * Clears the enable flag that func_000B5FD0 tests first; func_000B5FB0 sets it to 1.
 * Address: UFO2P.EXE 0x000B5FC0
 * Evidence: call: 0x000B5FD0 returns at once while 0x00135818 is 0; this stores 0 there
 * Evidence: call: 0x000B5FB0, its neighbour, stores 1 in 0x00135818 (the enable half)
 * Evidence: call: callers include main, 0x00089980, 0x0008A1E0, 0x000A3BA0, 0x000A49D0, 0x000BA360
 */
void level_update_disable(void)
{
    is_level_update_enabled = 0;
}

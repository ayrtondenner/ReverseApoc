/*
 * src/ufo2p/u_00060c50.c: translation unit u_00060c50 of UFO2P.EXE, 0x00060C50..0x000623A0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00060c50`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00060C50);
INCLUDE_ASM(func_00060C80);
INCLUDE_ASM(func_00060F50);
INCLUDE_ASM(func_00061200);
INCLUDE_ASM(func_00061550);
INCLUDE_ASM(func_00061F30);
INCLUDE_ASM(func_00061F50);
INCLUDE_ASM(func_00061FA0);
INCLUDE_ASM(func_00061FC0);
INCLUDE_ASM(func_00061FE0);
INCLUDE_ASM(func_000620C0);
INCLUDE_ASM(func_000621A0);
INCLUDE_ASM(func_000621D0);
INCLUDE_ASM(func_00062200);
INCLUDE_ASM(func_00062220);

extern int D_000E7304;

/* flag_e7304_set: set the flag at 0x000E7304
 * Stores 1 to the 32-bit global and returns; EAX is not set, so it returns nothing.
 * No direct caller is known; what the flag means is not read yet.
 * Address: UFO2P.EXE 0x00062210
 * Evidence: call: no direct caller; the body is one store of 1 to 0x000E7304, then ret
 */
void flag_e7304_set(void)
{
    D_000E7304 = 1;
}

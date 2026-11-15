/*
 * src/ufo2p/u_0004dfd0.c: translation unit u_0004dfd0 of UFO2P.EXE, 0x0004DFD0..0x0004E1C0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0004dfd0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0004DFF0);
INCLUDE_ASM(func_0004E0C0);

void func_0005EDF0(void);

extern int D_000E12F8;

void func_0004DFD0(void)
{
    unsigned i;

    i = 1;
    do {
        func_0005EDF0();
    } while (i < 0);
    D_000E12F8 = i;
}

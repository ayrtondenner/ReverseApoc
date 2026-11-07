/*
 * src/ufo2p/u_000989d0.c: translation unit u_000989d0 of UFO2P.EXE, 0x000989D0..0x0009A420 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000989d0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000989D0);
INCLUDE_ASM(func_00098A70);
INCLUDE_ASM(func_00099050);
INCLUDE_ASM(func_00099710);
INCLUDE_ASM(func_00099880);
INCLUDE_ASM(func_00099950);
INCLUDE_ASM(func_00099B50);
INCLUDE_ASM(func_00099CE0);
INCLUDE_ASM(func_00099DB0);
INCLUDE_ASM(func_0009A0A0);

extern int daily_history[27][56];

int func_00099830(int *a, int *b)
{
    int x;
    int y;

    x = daily_history[*a][0];
    y = daily_history[*b][0];
    if (x == 200) {
        x = 0;
    }
    if (y == 200) {
        y = 0;
    }
    return y - x;
}

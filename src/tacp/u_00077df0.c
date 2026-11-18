/*
 * src/tacp/u_00077df0.c: translation unit u_00077df0 of TACP.EXE, 0x00077DF0..0x00078130 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00077df0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00077DF0);
INCLUDE_ASM(func_00077F60);
extern unsigned char D_001B25C0;
extern volatile short D_001B25A4, D_001B25A6;
extern int D_00293020, D_00293024;
extern unsigned char D_002FF12E[];
void func_00077F60(void);
void func_00078130(void);

void func_000780C0(void)
{
    int index;

    if (D_001B25C0 && D_001B25A4 >= 0x26 && D_001B25A4 < 0x224 &&
        D_001B25A6 >= 0x5f && D_001B25A6 < 0x19f) {
        index = (D_001B25A6 - 0x5f) / 32;
        if (D_00293024 == 0 || D_002FF12E[index] != 0)
            D_00293020 = index;
        func_00077F60();
        func_00078130();
    }
}

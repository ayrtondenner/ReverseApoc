/*
 * src/ufo2p/u_000a31e0.c: translation unit u_000a31e0 of UFO2P.EXE, 0x000A31E0..0x000A34F0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000a31e0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000A31E0);
INCLUDE_ASM(func_000A3320);

extern unsigned char D_000D4CEA;
extern volatile short D_000D4CE0, D_000D4CE2;
extern int D_0012EFB4, D_0012EFB8;
extern unsigned char D_001C319E[];
void func_000A3320(void);
void func_000A34F0(void);

/* Return value is not established by the listing. */
void func_000A3480(void)
{
    int index;

    if (D_000D4CEA && D_000D4CE0 >= 0x26 && D_000D4CE0 < 0x224 &&
        D_000D4CE2 >= 0x5f && D_000D4CE2 < 0x19f) {
        index = (D_000D4CE2 - 0x5f) / 32;
        if (D_0012EFB8 == 0 || D_001C319E[index] != 0)
            D_0012EFB4 = index;
        func_000A3320();
        func_000A34F0();
    }
}

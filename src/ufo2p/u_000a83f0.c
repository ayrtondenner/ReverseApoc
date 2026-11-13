/*
 * src/ufo2p/u_000a83f0.c: translation unit u_000a83f0 of UFO2P.EXE, 0x000A83F0..0x000A8E10 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000a83f0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000A83F0);
INCLUDE_ASM(func_000A8700);
INCLUDE_ASM(func_000A8970);
INCLUDE_ASM(func_000A8B30);

extern volatile short D_000D4CE0;
extern volatile short D_000D4CE2;
extern short D_0012F00E;

/* Return value is not established by the listing. */
void func_000A8D70(void)
{
    if (D_000D4CE0 >= 0x25a && D_000D4CE0 < 0x27c &&
        D_000D4CE2 >= 0x1bb && D_000D4CE2 < 0x1dd) {
        D_0012F00E = 1;
    } else if (D_000D4CE0 >= 0x25a && D_000D4CE0 < 0x27c &&
               D_000D4CE2 >= 0x28 && D_000D4CE2 < 0x4a) {
        D_0012F00E = 2;
    } else if (D_000D4CE0 >= 0x25a && D_000D4CE0 < 0x27c &&
               D_000D4CE2 >= 0x50 && D_000D4CE2 < 0x72) {
        D_0012F00E = 3;
    }
}

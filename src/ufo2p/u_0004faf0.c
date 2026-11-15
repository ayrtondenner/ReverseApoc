/*
 * src/ufo2p/u_0004faf0.c: translation unit u_0004faf0 of UFO2P.EXE, 0x0004FAF0..0x000502B0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0004faf0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0004FAF0);
INCLUDE_ASM(func_0004FDB0);
INCLUDE_ASM(func_00050070);

struct unk_0002 {
    /* 0x00 */ s16 value;
}; /* size: 0x02 */

extern int D_000E12F0;
extern struct unk_0002 D_00183A22[];
void func_000977F0(int);

/* The return value is not used by the target. */
void func_00050290(void)
{
    short value;

    if (D_00183A22[D_000E12F0].value != 0) {
        value = D_00183A22[D_000E12F0].value;
        func_000977F0(value);
    }
}

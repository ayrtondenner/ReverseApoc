/*
 * src/ufo2p/u_000988c0.c: translation unit u_000988c0 of UFO2P.EXE, 0x000988C0..0x000989D0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000988c0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000988C0);

struct unk_0008 {
    /* 0x00 */ s32 unk_00;
    /* 0x04 */ s32 unk_04;
}; /* size: 0x08 */

extern struct unk_0008 D_000E0C5C[];

/* void: EAX holds only the masked index at ret; the callers decide. */
void stat_tally_add(u16 idx, s32 delta)
{
    D_000E0C5C[idx].unk_00 += delta;
}

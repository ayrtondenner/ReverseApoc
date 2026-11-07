/*
 * src/ufo2p/u_00050c60.c: translation unit u_00050c60 of UFO2P.EXE, 0x00050C60..0x00050D30 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00050c60`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00050C60);
INCLUDE_ASM(func_00050C90);

extern int D_000D5054;
struct unk_0004 {
    /* 0x00 */ s32 value;
}; /* size: 0x04 */

extern struct unk_0004 D_00182A20[];
extern short hover_info_changed;

/* void: EAX only holds a scaled index at ret, the bytes cannot tell. */
void func_00050D00(void)
{
    if (D_00182A20[D_000D5054].value > 0) {
        D_00182A20[D_000D5054].value--;
    }
    hover_info_changed = 1;
}

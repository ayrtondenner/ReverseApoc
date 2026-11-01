/*
 * src/ufo2p/u_0002e710.c: translation unit u_0002e710 of UFO2P.EXE, 0x0002E710..0x0002ED30 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0002e710`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0002E710);
INCLUDE_ASM(func_0002E880);
INCLUDE_ASM(func_0002EA00);
INCLUDE_ASM(func_0002EC30);

struct unk_000C {
    /* 0x00 */ s32 a;
    /* 0x04 */ s32 b;
    /* 0x08 */ s32 c;
}; /* size: 0x0C */

extern short hover_info_changed;
extern struct unk_000C hover_info_shown;

void hover_info_publish(struct unk_000C *p)
{
    hover_info_changed = 1;
    hover_info_shown = *p;
}

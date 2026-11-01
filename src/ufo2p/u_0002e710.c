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

/*
 * The record the mouse hover code at 0x000505A0 keeps at 0x001A3C80: where the pointer rests,
 * when it came to rest there, and what lies under it.
 */
struct hover_info {
    /* 0x00 */ s16 x;          /* pointer x, copied from 0x000D4CE0 */
    /* 0x02 */ s16 y;          /* pointer y, copied from 0x000D4CE2 */
    /* 0x04 */ s32 rest_time;  /* the clock (0x00011430) when the pointer stopped */
    /* 0x08 */ void *target;   /* what lies under the pointer, 0 for nothing */
}; /* size: 0x0C */

extern short hover_info_changed;
extern struct hover_info hover_info_shown;

/* hover_info_publish: publish the current hover record
 * Copies the caller's hover record into the shown one and raises the changed flag.
 * Address: UFO2P.EXE 0x0002ED10
 * Evidence: call: 0x000505A0 calls it with 0x001A3C80 once the pointer rests 5 clock ticks over a target
 * Evidence: call: 0x000505A0 also sets the 16-bit flag 0x00183A78 to 1 when the pointer leaves a target
 */
void hover_info_publish(struct hover_info *info)
{
    hover_info_changed = 1;
    hover_info_shown = *info;
}

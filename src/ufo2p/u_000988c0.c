/*
 * src/ufo2p/u_000988c0.c: translation unit u_000988c0 of UFO2P.EXE, 0x000988C0..0x000989D0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000988c0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000988C0);

/* One 8-byte tally record; the callers pass a small category number as the index. */
struct stat_tally_rec {
    /* 0x00 */ s32 amount; /* running total that stat_tally_add adds to */
    /* 0x04 */ s32 aux_04;  /* not written here; meaning unknown */
}; /* size: 0x08 */

extern struct stat_tally_rec stat_tally_table[];

/* stat_tally_add: add an amount to one tally category
 * Adds delta to the first dword of record category of stat_tally_table.
 * void: EAX holds only the masked index at ret; the callers ignore it.
 * Address: UFO2P.EXE 0x000989C0
 * Evidence: call: 0x000AB720 calls it with category 1 and a per-entry word once an entry's progress reaches its target
 * Evidence: call: 0x000B3FA0 calls it with category 0 and with category 7, each with an amount it loads first
 */
void stat_tally_add(u16 category, s32 delta)
{
    stat_tally_table[category].amount += delta;
}

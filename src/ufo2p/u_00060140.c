/*
 * src/ufo2p/u_00060140.c: translation unit u_00060140 of UFO2P.EXE, 0x00060140..0x000602E0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00060140`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00060140);

#define REC276_SLOT_COUNT 3
#define REC276_SLOT_EMPTY -1
#define REC276_KIND_COUNTS_AS_ONE 0x21
#define REC276_HEAD_BYTES 0x4
#define REC276_BODY_BYTES 0x114

/*
 * One 0x276-byte record of the table the caller func_000602E0 walks from D_00160FD8 to
 * D_0016D4B8. Only the fields this unit reads are named.
 */
struct rec276 {
    /* 0x000 */ u8 head_000[REC276_HEAD_BYTES];
    /* 0x004 */ s16 kind;
    /* 0x006 */ u8 body_006[REC276_BODY_BYTES];
    /* 0x11A */ s16 slots[REC276_SLOT_COUNT];
}; /* size: 0x276 per the caller's stride (only read up to 0x120 here) */

/* rec276_count_filled_slots: count the filled slots of one record
 * Counts how many of the three s16 slots at +0x11A are not -1; a record whose
 * s16 kind at +0x04 is 0x21 counts as exactly one, whatever its slots hold.
 * Address: UFO2P.EXE 0x000602A0
 * Evidence: call: caller 0x000602E0 passes each 0x276-byte record from 0x00160FD8 and skips it when this returns 0
 * Evidence: table: the records start at 0x00160FD8 and end at 0x0016D4B8, stride 0x276
 */
short rec276_count_filled_slots(struct rec276 *rec)
{
    short count;
    short slot;

    count = 0;
    slot = 0;
    do {
        count += rec->slots[slot] != REC276_SLOT_EMPTY;
        slot++;
    } while (slot < REC276_SLOT_COUNT);
    if (rec->kind == REC276_KIND_COUNTS_AS_ONE) {
        count = 1;
    }
    return count;
}

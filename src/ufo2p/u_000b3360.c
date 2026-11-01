/*
 * src/ufo2p/u_000b3360.c: translation unit u_000b3360 of UFO2P.EXE, 0x000B3360..0x000B33A0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000b3360`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

#define SLOT_RECORD_COUNT 180
#define SLOT_RECORD_EMPTY -1
#define SLOT_NOT_FOUND -1

/* One 0xCE-byte record of the slot table at 0x00144918. Only the fields read here are named. */
struct slot_record {
    /* 0x00 */ u8 opaque_00[0x1A]; /* lit: gap size up to the id field; its contents are not read here */
    /* 0x1A */ u16 id;
    /* 0x1C */ u8 opaque_1C[0x61]; /* lit: gap size up to the state field; its contents are not read here */
    /* 0x7D */ s8 state; /* SLOT_RECORD_EMPTY marks an unused slot */
    /* 0x7E */ u8 opaque_7E[0x50]; /* lit: tail size up to the 0xCE stride; its contents are not read here */
}; /* size: 0xCE */

extern struct slot_record slot_table_records[];

/* slot_table_find_by_id: find the slot index holding an id
 * Scans the 180 records of the slot table, skips unused ones (state -1) and returns the
 * index of the first record whose u16 id equals the argument, or -1 when none does.
 * Address: UFO2P.EXE 0x000B3360
 * Evidence: call: 0x000B34A0 passes a u16 id, then bounds the result to 0..0xB3 and indexes 0x00144918 by 0xCE
 * Evidence: table: 0x00144918 holds 180 records of 0xCE bytes, a u16 id at +0x1A, -1 at +0x7D marks unused
 */
int slot_table_find_by_id(int id)
{
    int slot;
    int found;
    struct slot_record *record;

    found = SLOT_NOT_FOUND;
    record = slot_table_records;
    slot = 0;
    do {
        if (record->state != SLOT_RECORD_EMPTY && record->id == id) {
            found = slot;
            break;
        }
        slot++;
        record++;
    } while (slot < SLOT_RECORD_COUNT);
    return found;
}

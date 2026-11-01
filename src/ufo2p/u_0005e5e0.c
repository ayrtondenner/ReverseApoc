/*
 * src/ufo2p/u_0005e5e0.c: translation unit u_0005e5e0 of UFO2P.EXE, 0x0005E5E0..0x0005E910 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0005e5e0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0005E610);
INCLUDE_ASM(func_0005E650);
INCLUDE_ASM(func_0005E690);

/* Number of entries in the slot table at 0x0014D9F0 (the loop bound, 0x12C). */
#define SLOT_TABLE_COUNT 300
/* Bytes of an entry after its id; the entry is 0x10 bytes (the pointer step). */
#define SLOT_ENTRY_REST_SIZE 0x0E

/* One 16-byte entry of the slot table; only the leading s16 id is read here. */
struct slot_entry {
    /* 0x00 */ s16 id;
    /* 0x02 */ u8 rest_02[SLOT_ENTRY_REST_SIZE];
}; /* size: 0x10 */

extern struct slot_entry slot_table[];

/* slot_table_has_zero_id: report whether any slot has id zero
 * Walks all 300 entries of the table at 0x0014D9F0 and returns 1 at the first
 * entry whose s16 id is 0, else 0. What a zero id means is not known yet.
 * Address: UFO2P.EXE 0x0005E5E0
 * Evidence: table: scans 300 entries of 0x10 bytes at 0x0014D9F0, testing the s16 at offset 0 against 0
 * Evidence: call: the main loop 0x00010940 tests it after 0x0005E5B0 and before 0x0005E610 at 0x00011307
 */
int slot_table_has_zero_id(void)
{
    s16 index;
    int has_zero_id;
    struct slot_entry *entry;

    entry = slot_table;
    has_zero_id = 0;
    index = 0;
    do {
        if (entry->id == 0) {
            has_zero_id = 1;
            break;
        }
        index++;
        entry++;
    } while (index < SLOT_TABLE_COUNT);
    return has_zero_id;
}

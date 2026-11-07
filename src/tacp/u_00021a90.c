/*
 * src/tacp/u_00021a90.c: translation unit u_00021a90 of TACP.EXE, 0x00021A90..0x00023C00 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00021a90`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00021A90);
INCLUDE_ASM(func_00021B30);
INCLUDE_ASM(func_00021BB0);
INCLUDE_ASM(func_00021E30);
INCLUDE_ASM(func_00021FD0);
INCLUDE_ASM(func_00022110);
INCLUDE_ASM(func_00022140);
INCLUDE_ASM(func_00022210);
INCLUDE_ASM(func_000222A0);
INCLUDE_ASM(func_000225E0);
INCLUDE_ASM(func_00022670);
INCLUDE_ASM(func_00022A30);
INCLUDE_ASM(func_00023010);
INCLUDE_ASM(func_00023130);
INCLUDE_ASM(func_00023150);
INCLUDE_ASM(func_00023190);
INCLUDE_ASM(func_00023720);
INCLUDE_ASM(func_00023890);
INCLUDE_ASM(func_00023940);
INCLUDE_ASM(func_00023A40);
INCLUDE_ASM(func_00023AA0);
INCLUDE_ASM(func_00023BB0);

extern signed char D_001D3428[][28];
extern signed char D_002818B9;

int func_00021B70(short a, short b)
{
    int result;

    result = 0;
    if ((short)D_001D3428[a][b] >= (short)D_002818B9) {
        result = 1;
    }
    return result;
}

struct unk_000D {
    /* 0x00 */ u8 pad_00[2];
    /* 0x02 */ s8 byte_02;
    /* 0x03 */ u8 pad_03[9];
    /* 0x0C */ s8 byte_0C;
}; /* size: 0x0D (at least) */

struct unk_0012 {
    /* 0x00 */ u8 pad_00[2];
    /* 0x02 */ u8 kind;
    /* 0x03 */ u8 index;
    /* 0x04 */ u8 pad_04[0x0E];
}; /* size: 0x12 */

struct unk_0010 {
    /* 0x00 */ s8 key[3];
    /* 0x03 */ s8 value[3];
    /* 0x06 */ u8 pad_06[0x0A];
}; /* size: 0x10 */

struct unk_000C {
    /* 0x00 */ s8 value;
    /* 0x01 */ u8 pad_01[0x0B];
}; /* size: 0x0C */

extern struct unk_0012 D_002B2852[];
extern struct unk_0010 D_002B2612[];
extern struct unk_000C D_002B2E71[];

int func_00021F50(struct unk_000D *p)
{
    struct unk_0012 *entry;
    struct unk_0010 *table;
    int i;
    int result;

    result = 0;
    entry = &D_002B2852[p->byte_02];
    if (entry->kind == 1) {
        table = &D_002B2612[entry->index];
        for (i = 0; i < 3; i++) {
            if (table->key[i] == p->byte_0C) {
                result = table->value[i];
            }
        }
    } else if (entry->kind == 2) {
        result = D_002B2E71[entry->index].value;
    }
    if (result == 0) {
        result = -1;
    }
    return result;
}

struct unk_00D0 {
    /* 0x00 */ u8 pad_00[0xAE];
    /* 0xAE */ s16 word_AE;
    /* 0xB0 */ u8 pad_B0[0x0E];
    /* 0xBE */ s16 word_BE;
    /* 0xC0 */ u8 pad_C0[0x0E];
    /* 0xCE */ s16 word_CE;
}; /* size: 0xD0 (at least) */

extern int D_000E4C18;

int func_00022060(struct unk_00D0 *p)
{
    int value;
    int percent;

    value = p->word_AE;
    percent = p->word_BE % 40 + p->word_CE - 40;
    if (percent < 0) {
        percent = 0;
    } else {
        percent = percent * 100 / p->word_CE;
    }
    if (percent > 50) {
        value++;
    }
    percent = D_000E4C18 - 1;
    if (value < percent) {
        percent = value;
    }
    return percent;
}

/* Slots per record: the loop below walks 6 slot bytes at +0x27A and 6 flags at +0x280. */
#define TACREC_SLOT_COUNT 6
/* The s16 at +0 of a free tacrec_table record. */
#define TACREC_ID_FREE -1

/* One 0x49C-byte record of the table tacrec_table (the stride of every index into it). */
struct tacrec_entry {
    /* 0x000 */ s16 id; /* TACREC_ID_FREE when the record is free */
    /* 0x002 */ u8 unread_002[0x49A]; /* lit: layout gap up to the 0x49C stride */
}; /* size: 0x49C */

/*
 * The same 0x49C-byte record seen from tacrec_count_live_slots: the caller at 0x0003C90F passes a
 * pointer into tacrec_table. Only the fields tacrec_count_live_slots reads are named.
 */
struct tacrec_slots {
    /* 0x000 */ u8 unread_000[0x64]; /* lit: layout gap up to +0x64 */
    /* 0x064 */ s16 word_064; /* the caller at 0x0003C347 skips the call when it is 0 */
    /* 0x066 */ u8 unread_066[0x1A]; /* lit: layout gap up to +0x80 */
    /* 0x080 */ s16 word_080;
    /* 0x082 */ u8 unread_082[0x1F8]; /* lit: layout gap up to +0x27A */
    /* 0x27A */ u8 slot_record[TACREC_SLOT_COUNT]; /* index into tacrec_table */
    /* 0x280 */ u8 slot_is_used[TACREC_SLOT_COUNT];
}; /* size: 0x286 (at least) */

extern struct tacrec_entry tacrec_table[];

/* tacrec_count_live_slots: count the used slots that reference live records
 * Returns 0 unless word_064 is greater than word_080. Otherwise counts the slots whose
 * used flag is set and whose tacrec_table record has an id other than TACREC_ID_FREE.
 * Address: TACP.EXE 0x000220C0
 * Evidence: table: indexes the 0x49C-byte records of tacrec_table by the slot bytes at +0x27A
 * Evidence: call: 0x0003C600 passes a pointer into tacrec_table and tests the returned count for 0
 * Evidence: call: 0x0003C180 calls it only when the s16 at +0x64 is non-zero and uses a count above 0
 */
int tacrec_count_live_slots(struct tacrec_slots *rec)
{
    int count;
    int slot;

    count = 0;
    if (rec->word_064 > rec->word_080) {
        for (slot = 0; slot < TACREC_SLOT_COUNT; slot++) {
            if (rec->slot_is_used[slot] != 0
                && tacrec_table[rec->slot_record[slot]].id != TACREC_ID_FREE) {
                count++;
            }
        }
    }
    return count;
}

/*
 * src/ufo2p/u_000ab080.c: translation unit u_000ab080 of UFO2P.EXE, 0x000AB080..0x000AB720 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000ab080`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000AB090);
INCLUDE_ASM(func_000AB240);
INCLUDE_ASM(func_000AB5F0);

/* Size not known: only the fields up to 0x7F are read here. */
struct unk_0080 {
    /* 0x00 */ u8 pad_00[0x21];
    /* 0x21 */ u8 unk_21;
    /* 0x22 */ u8 pad_22;
    /* 0x23 */ u8 unk_23;
    /* 0x24 */ s16 unk_24;
    /* 0x26 */ u8 pad_26[0x15];
    /* 0x3B */ u8 unk_3B;
    /* 0x3C */ u8 unk_3C;
    /* 0x3D */ u8 pad_3D[0x3F];
    /* 0x7C */ u8 unk_7C;
    /* 0x7D */ u8 unk_7D;
    /* 0x7E */ s16 unk_7E;
};

struct unk_02BE {
    /* 0x000 */ s16 unk_000;
    /* 0x002 */ u8 pad_002[0x2BC];
}; /* size: 0x2BE */

extern u8 D_000D5060;
extern struct unk_02BE D_000D942E[];

/* Defined above func_000AB6A0: under -oneatx wcc386 pads a function that has another
 * after it, and func_000AB6A0's row holds no padding. */
int func_000AB6D0(struct unk_0080 *arg0)
{
    int result;

    result = 0;
    if (arg0->unk_7D == 1 && arg0->unk_7C == D_000D5060 && arg0->unk_21 == 0
        && arg0->unk_23 != 0 && arg0->unk_7E == D_000D942E[arg0->unk_24].unk_000
        && arg0->unk_3C == arg0->unk_3B) {
        result = 1;
    }
    return result;
}

/* An id of -1 names no flag record (a rule input left unused). */
#define FLAG_ID_NONE -1
/* State of an unused input: non-zero, so an AND-style rule ignores it, but not
 * positive as a signed char, so an OR-style rule ignores it too. */
#define FLAG_STATE_UNUSED 0xff

/* One 10-byte flag record; only byte 0 (set or clear) is read in this unit. */
struct flag_record {
    /* 0x00 */ u8 is_set;
    /* 0x01 */ u8 rest_01[9]; /* lit: bytes 1..9 of the record, not read in this unit */
}; /* size: 0x0A */

extern struct flag_record flag_records[];

/* flag_record_state: report one flag record state
 * Returns 1 when the record's byte 0 is set, FLAG_STATE_UNUSED (0xff) for the id -1
 * and 0 otherwise.
 * BUG(original): for id -1 it still reads record[-1], and returns 1 if that byte is set.
 * Address: UFO2P.EXE 0x000AB6A0
 * Evidence: call: func_000AB090 calls it on the 16-bit ids at +0xE and +0x10 of a 0x32-byte rule at 0x000DE690
 * Evidence: call: func_000AB090 inlines the same test on the id at +0xC and combines the three by the rule's op byte
 * Evidence: table: 0x000DE2B8 holds 10-byte records indexed by that id; byte 0 is the flag
 */
char flag_record_state(int flag_id)
{
    char state;

    state = 0;
    if ((short)flag_id == FLAG_ID_NONE) {
        state = FLAG_STATE_UNUSED;
    }
    if (flag_records[(short)flag_id].is_set != 0) {
        state = 1;
    }
    return state;
}
